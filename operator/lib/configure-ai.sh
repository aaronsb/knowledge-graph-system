#!/bin/bash
# configure-ai.sh — shared AI extraction-provider configuration.
#
# Single source of truth for: choosing an AI extraction provider, validating +
# storing its API key, and selecting an extraction model. Sourced by:
#   - operator/lib/guided-init.sh    (operator.sh init, interactive)
#   - operator/lib/headless-init.sh  (operator.sh init --headless)
#   - install.sh                     (curl|bash standalone installer)
#
# Every provider interaction is delegated to the operator container's
# configure.py — which validates keys server-side with the real provider SDK and
# enumerates models live from each provider's API (ADR-800/801). Nothing here
# talks to a provider over ad-hoc curl, so there is exactly one place that knows
# each provider's contract and the three callers can never drift apart.
#
# Reads come from /dev/tty so the interactive prompts work even when the calling
# script is piped through `curl | bash` (its stdin is the script, not the user).
#
# @verified cbd07870c

# Color fallbacks — callers normally export these; stay readable standalone.
: "${RED:=\033[0;31m}"
: "${GREEN:=\033[0;32m}"
: "${YELLOW:=\033[1;33m}"
: "${BLUE:=\033[0;34m}"
: "${BOLD:=\033[1m}"
: "${NC:=\033[0m}"

# Docker command prefix. The operator init scripts run docker directly; the
# standalone install.sh runs it via sudo, so it sets CAI_DOCKER="sudo docker"
# before sourcing. Left unquoted at the call site so a multi-word value splits.
: "${CAI_DOCKER:=docker}"

# _cai_op <container> <configure.py args...>
# Run a configure.py subcommand inside the operator container.  @verified cbd07870c
_cai_op() {
    local container="$1"; shift
    $CAI_DOCKER exec "$container" python /workspace/operator/configure.py "$@"
}

# cai_select_provider — interactive AI provider menu.
# Sets the global AI_PROVIDER to one of: openai | anthropic | openrouter.
# Ollama is intentionally omitted (local inference, configured post-setup).
# @verified cbd07870c
cai_select_provider() {
    echo "Choose your AI extraction provider:"
    echo ""
    echo -e "  ${GREEN}[1] OpenAI${NC} (GPT-4o, GPT-4o-mini)"
    echo -e "  ${GREEN}[2] Anthropic${NC} (Claude Sonnet / Opus / Haiku)"
    echo -e "  ${GREEN}[3] OpenRouter${NC} (200+ models, single key)"
    echo ""
    echo -e "  ${YELLOW}Note:${NC} Ollama (local inference) can be configured later"
    echo "        via: ./operator.sh shell → configure ai-provider ollama"
    echo ""
    local reply
    read -p "Choose option (1-3) [1]: " -r reply </dev/tty
    echo ""
    case "$reply" in
        2) AI_PROVIDER="anthropic" ;;
        3) AI_PROVIDER="openrouter" ;;
        *) AI_PROVIDER="openai" ;;
    esac
    echo -e "${GREEN}→${NC} Selected ${AI_PROVIDER}"
    echo ""
}

# cai_store_api_key <container> <provider> [preset_key]
# Store and validate the provider API key via `configure.py api-key`, which does
# the real server-side validation. With preset_key, applies it once and returns
# the configure.py exit code. Without it, prompts and loops until a key validates.
# @verified cbd07870c
cai_store_api_key() {
    local container="$1" provider="$2" preset_key="${3:-}"
    local key

    if [ -n "$preset_key" ]; then
        _cai_op "$container" api-key "$provider" --key "$preset_key"
        return $?
    fi

    echo "Enter your ${provider} API key — it will be validated and stored encrypted."
    echo -e "${YELLOW}Press Ctrl+C to cancel.${NC}"
    echo ""
    while true; do
        read -p "${provider} API key: " -r key </dev/tty
        echo ""
        if [ -z "$key" ]; then
            echo -e "${RED}✗${NC} API key cannot be empty. Please try again."
            echo ""
            continue
        fi
        echo -e "${BLUE}→${NC} Validating and storing API key..."
        if _cai_op "$container" api-key "$provider" --key "$key" 2>&1; then
            echo ""
            return 0
        fi
        echo ""
        echo -e "${RED}✗${NC} Validation failed. Check the key and try again."
        echo ""
    done
}

# cai_select_model <container> <provider>
# Refresh the live model catalog and run the interactive picker (curated/all
# toggle + price sort), then persist the choice: models enable/default and
# ai-provider --model --max-tokens. Falls back to the provider default and
# returns 0 if the catalog can't be fetched.
# @verified cbd07870c
cai_select_model() {
    local container="$1" provider="$2"

    # Seed provider config with its default model so catalog refresh can run.
    _cai_op "$container" ai-provider "$provider" 2>/dev/null

    echo -e "${BLUE}→${NC} Fetching available models from ${provider}..."
    _cai_op "$container" models refresh "$provider" 2>&1
    echo ""

    local FULL_MODEL_LIST
    FULL_MODEL_LIST=$(_cai_op "$container" models list "$provider" --tsv --category extraction 2>/dev/null)

    if [ -z "$FULL_MODEL_LIST" ]; then
        echo -e "${YELLOW}⚠${NC} Could not fetch models from catalog. Using provider default."
        echo ""
        return 0
    fi

    # Curation regex per provider. Now that ADR-800/801 enumerates models live
    # from each provider's API, OpenAI/Anthropic also return 30+ entries — the
    # old assumption that their seed lists were already curated no longer holds.
    # Default the picker to the latest production families and let the [0] toggle
    # reveal the full catalog.
    local CURATED_PATTERN
    case "$provider" in
        openai)
            CURATED_PATTERN='(gpt-4o|gpt-4\.5|gpt-5|o1|o3)'
            ;;
        anthropic)
            CURATED_PATTERN='(claude-(sonnet|opus|haiku)-4|claude-3-5-(sonnet|haiku))'
            ;;
        openrouter)
            CURATED_PATTERN='(gpt-4o|gpt-4\.5|gpt-5|claude.*sonnet|claude.*opus|claude.*haiku|gemini.*pro|gemini.*flash|llama.*70|llama.*405|qwen.*72|mistral.*large|deepseek.*chat|deepseek.*r1|command-r)'
            ;;
        *)
            CURATED_PATTERN=""
            ;;
    esac

    local MODEL_LIST
    if [ -n "$CURATED_PATTERN" ]; then
        MODEL_LIST=$(echo "$FULL_MODEL_LIST" | grep -iE "$CURATED_PATTERN")
        # Empty curation (regex matched nothing) → fall back to the full list
        # rather than showing an empty menu.
        if [ -z "$MODEL_LIST" ]; then
            MODEL_LIST="$FULL_MODEL_LIST"
            CURATED_PATTERN=""
        fi
    else
        MODEL_LIST="$FULL_MODEL_LIST"
    fi

    # Sort a TSV model list by prompt price (column 4).
    # Args: $1=model_list, $2=sort mode ("asc", "desc", or "none")
    sort_model_list() {
        local list="$1" mode="$2"
        case "$mode" in
            asc)  echo "$list" | sort -t$'\t' -k4 -n ;;
            desc) echo "$list" | sort -t$'\t' -k4 -rn ;;
            *)    echo "$list" ;;
        esac
    }

    # Build numbered menu from filtered list.
    display_model_menu() {
        local model_list="$1"
        MENU_INDEX=0
        declare -g -a MODEL_IDS MODEL_NAMES MODEL_CATALOG_IDS MODEL_PRICES
        MODEL_IDS=()
        MODEL_NAMES=()
        MODEL_CATALOG_IDS=()
        MODEL_PRICES=()

        while IFS=$'\t' read -r cat_id model_id display_name prompt_price comp_price; do
            MENU_INDEX=$((MENU_INDEX + 1))
            MODEL_CATALOG_IDS[$MENU_INDEX]="$cat_id"
            MODEL_IDS[$MENU_INDEX]="$model_id"
            MODEL_NAMES[$MENU_INDEX]="$display_name"

            if [ -n "$prompt_price" ] && [ "$prompt_price" != "0.0000" ]; then
                MODEL_PRICES[$MENU_INDEX]="\$${prompt_price}/\$${comp_price} per 1M tokens"
            else
                MODEL_PRICES[$MENU_INDEX]="free (local)"
            fi

            printf "  ${GREEN}[%2d]${NC} %-45s %s\n" "$MENU_INDEX" "$display_name" "${MODEL_PRICES[$MENU_INDEX]}"
        done <<< "$model_list"
    }

    # State for the selection loop.
    local SHOW_ALL=false
    local SORT_MODE="none"  # none → asc → desc → none
    local CURRENT_LIST="$MODEL_LIST"

    redisplay_menu() {
        # Pick base list.
        local base
        if [ "$SHOW_ALL" = true ]; then
            base="$FULL_MODEL_LIST"
        else
            base="$MODEL_LIST"
        fi
        CURRENT_LIST=$(sort_model_list "$base" "$SORT_MODE")

        echo ""
        if [ "$SHOW_ALL" = true ]; then
            echo "All available models:"
        else
            echo "Available extraction models:"
        fi
        # Show sort indicator.
        case "$SORT_MODE" in
            asc)  echo -e "  ${YELLOW}(sorted: cheapest first)${NC}" ;;
            desc) echo -e "  ${YELLOW}(sorted: most expensive first)${NC}" ;;
        esac
        echo ""
        display_model_menu "$CURRENT_LIST"

        # Show options footer.
        echo ""
        if [ -n "$CURATED_PATTERN" ]; then
            TOTAL_COUNT=$(echo "$FULL_MODEL_LIST" | wc -l)
            if [ "$SHOW_ALL" = true ]; then
                echo -e "  ${YELLOW}[ 0]${NC} Show curated models only"
            else
                echo -e "  ${YELLOW}[ 0]${NC} Show all ${TOTAL_COUNT} available models"
            fi
        fi
        case "$SORT_MODE" in
            none) echo -e "  ${YELLOW}[ \$]${NC} Sort by price (cheapest first)" ;;
            asc)  echo -e "  ${YELLOW}[ \$]${NC} Sort by price (most expensive first)" ;;
            desc) echo -e "  ${YELLOW}[ \$]${NC} Clear price sort" ;;
        esac
        echo ""
    }

    # Initial display.
    redisplay_menu

    local SELECTING=true MODEL_CHOICE
    while [ "$SELECTING" = true ]; do
        read -p "Choose model (1-${MENU_INDEX}) [1]: " -r MODEL_CHOICE </dev/tty
        if [ -z "$MODEL_CHOICE" ]; then
            MODEL_CHOICE=1
        fi

        # Handle "show all / show curated" toggle (any provider with curation).
        if [ "$MODEL_CHOICE" = "0" ] && [ -n "$CURATED_PATTERN" ]; then
            if [ "$SHOW_ALL" = true ]; then
                SHOW_ALL=false
            else
                SHOW_ALL=true
            fi
            redisplay_menu
            continue
        fi

        # Handle price sort toggle.
        if [ "$MODEL_CHOICE" = '$' ]; then
            case "$SORT_MODE" in
                none) SORT_MODE="asc" ;;
                asc)  SORT_MODE="desc" ;;
                desc) SORT_MODE="none" ;;
            esac
            redisplay_menu
            continue
        fi

        # Validate and apply choice.
        if [ "$MODEL_CHOICE" -ge 1 ] 2>/dev/null && [ "$MODEL_CHOICE" -le "$MENU_INDEX" ] 2>/dev/null; then
            local CHOSEN_MODEL_ID="${MODEL_IDS[$MODEL_CHOICE]}"
            local CHOSEN_CATALOG_ID="${MODEL_CATALOG_IDS[$MODEL_CHOICE]}"
            local CHOSEN_NAME="${MODEL_NAMES[$MODEL_CHOICE]}"

            echo ""
            echo -e "${GREEN}→${NC} Selected: ${BOLD}${CHOSEN_NAME}${NC} (${CHOSEN_MODEL_ID})"

            # Prompt for max completion tokens with sensible default.
            echo ""
            local MAX_TOKENS_INPUT MAX_TOKENS
            read -p "Max completion tokens [16384]: " -r MAX_TOKENS_INPUT </dev/tty
            MAX_TOKENS="${MAX_TOKENS_INPUT:-16384}"
            echo -e "${GREEN}→${NC} Max tokens: ${MAX_TOKENS}"

            # Enable and set as default in catalog.
            _cai_op "$container" models enable "$CHOSEN_CATALOG_ID" 2>/dev/null
            _cai_op "$container" models default "$CHOSEN_CATALOG_ID" 2>/dev/null

            # Update active extraction config with chosen model and max tokens.
            _cai_op "$container" ai-provider "$provider" --model "$CHOSEN_MODEL_ID" --max-tokens "$MAX_TOKENS"
            SELECTING=false
        else
            echo -e "${YELLOW}→${NC} Invalid choice, please try again."
        fi
    done
}

# cai_configure_interactive <container> [provider]
# End-to-end interactive flow: select provider (unless one is passed), store +
# validate the key, then pick the model. Used by guided-init.sh and install.sh.
# @verified cbd07870c
cai_configure_interactive() {
    local container="$1" provider="${2:-}"
    if [ -z "$provider" ]; then
        cai_select_provider
        provider="$AI_PROVIDER"
    fi
    cai_store_api_key "$container" "$provider"
    cai_select_model "$container" "$provider"
}

# cai_apply_headless <container> [provider] [key] [model]
# Non-interactive application of preset values (operator --headless, install
# --ai-* flags). With no provider, sets the OpenAI default with no key.
# @verified cbd07870c
cai_apply_headless() {
    local container="$1" provider="${2:-}" key="${3:-}" model="${4:-}"

    if [ -z "$provider" ]; then
        _cai_op "$container" ai-provider openai --model gpt-4o
        return 0
    fi

    local model_arg=()
    [ -n "$model" ] && model_arg=(--model "$model")
    _cai_op "$container" ai-provider "$provider" "${model_arg[@]}"
    [ -n "$key" ] && _cai_op "$container" api-key "$provider" --key "$key"
}
