#!/bin/bash
# ============================================================================
# publish-wizard.sh - Interactive release wizard for Knowledge Graph System
# ============================================================================
WIZARD_VERSION="0.6.6"
# ============================================================================
#
# An interactive wizard that guides through the release process.
# Orchestrates calls to publish.sh - does not duplicate its logic.
#
# ARCHITECTURE:
# -------------
#   1. CONFIGURATION    - Defaults and saved preferences
#   2. UTILITIES        - Colors, logging, prompts
#   3. AUTH HELPERS     - Check/verify authentication status
#   4. WIZARD STEPS     - Each step of the interactive flow
#   5. MAIN             - Entry point
#
# USAGE:
#   ./publish-wizard.sh              # Run interactive wizard
#   ./publish-wizard.sh --reset      # Clear saved preferences
#   ./publish-wizard.sh --help       # Show help
#
# RELATIONSHIP TO publish.sh:
#   This wizard calls publish.sh for all actual operations:
#     - ./publish.sh status          (get current versions)
#     - ./publish.sh release ...     (bump, commit, tag)
#     - ./publish.sh images ...      (build and push)
#     - ./publish.sh cli ...         (npm publish)
#     - ./publish.sh fuse ...        (pypi publish)
#
# ============================================================================

set -e

# ============================================================================
# SECTION 1: CONFIGURATION
# ============================================================================

# --- Paths ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PUBLISH_SH="$SCRIPT_DIR/publish.sh"

# --- Config File ---
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/knowledge-graph"
CONFIG_FILE="$CONFIG_DIR/publish-wizard.conf"

# --- Defaults (can be overridden by saved config) ---
DEFAULT_BUMP_TYPE="patch"
PUBLISH_IMAGES=true
PUBLISH_CLI=false
PUBLISH_FUSE=false
USE_MULTI_ARCH=true

# --- Runtime State ---
CURRENT_VERSION=""
NEW_VERSION=""
RELEASE_MESSAGE=""
BUMP_TYPE=""

# --- Detected State (populated by check functions) ---
CLI_VERSION=""
CLI_PUBLISHED=""
FUSE_VERSION=""
FUSE_PUBLISHED=""
IMAGES_PUBLISHED=""
COMMITS_SINCE_TAG=""

# ============================================================================
# SECTION 2: UTILITIES
# ============================================================================

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# --- Logging ---
log_step() {
    echo -e "\n${CYAN}━━━ $1 ━━━${NC}"
}

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

# --- Prompts ---
prompt_value() {
    # Prompt for text input with optional default
    # Usage: result=$(prompt_value "Prompt" "default")
    local prompt="$1"
    local default="$2"
    local response

    if [[ -n "$default" ]]; then
        echo -ne "${CYAN}?${NC} ${prompt} [${default}]: " >&2
    else
        echo -ne "${CYAN}?${NC} ${prompt}: " >&2
    fi

    read -r response </dev/tty
    echo "${response:-$default}"
}

prompt_bool() {
    # Prompt for yes/no with default
    # Usage: if prompt_bool "Continue?" "y"; then ...
    local prompt="$1"
    local default="${2:-n}"
    local response

    if [[ "$default" == "y" ]]; then
        echo -ne "${CYAN}?${NC} ${prompt} [Y/n]: " >&2
    else
        echo -ne "${CYAN}?${NC} ${prompt} [y/N]: " >&2
    fi

    read -r response </dev/tty
    response="${response:-$default}"
    [[ "$response" =~ ^[Yy] ]]
}

prompt_select() {
    # Select from numbered list
    # Usage: result=$(prompt_select "Question" "opt1" "opt2" "opt3")
    local prompt="$1"
    shift
    local options=("$@")

    echo -e "\n${CYAN}?${NC} ${prompt}" >&2
    local i=1
    for opt in "${options[@]}"; do
        echo "   ${i}) ${opt}" >&2
        ((i++))
    done

    local selection
    echo -ne "   Choice [1]: " >&2
    read -r selection </dev/tty
    selection=${selection:-1}

    if [[ "$selection" -ge 1 && "$selection" -le ${#options[@]} ]]; then
        echo "${options[$((selection-1))]}"
    else
        echo "${options[0]}"
    fi
}

prompt_multiselect() {
    # Multi-select with toggles
    # Usage: prompt_multiselect "images|true" "cli|false" "fuse|false"
    # Modifies global variables based on item names
    local items=("$@")
    local selected=()
    local names=()

    # Parse items into names and initial states
    for item in "${items[@]}"; do
        local name="${item%%|*}"
        local state="${item##*|}"
        names+=("$name")
        selected+=("$state")
    done

    echo -e "\n${CYAN}?${NC} Select artifacts to publish (enter number to toggle, done to finish):" >&2

    while true; do
        echo "" >&2
        for i in "${!names[@]}"; do
            local checkbox="[ ]"
            [[ "${selected[$i]}" == "true" ]] && checkbox="[x]"
            echo "   $((i+1))) $checkbox ${names[$i]}" >&2
        done
        echo "   d) Done" >&2

        local choice
        echo -ne "   Toggle: " >&2
        read -r choice </dev/tty

        if [[ "$choice" == "d" || "$choice" == "done" ]]; then
            break
        elif [[ "$choice" =~ ^[0-9]+$ ]] && ((choice >= 1 && choice <= ${#names[@]})); then
            local idx=$((choice - 1))
            if [[ "${selected[$idx]}" == "true" ]]; then
                selected[$idx]="false"
            else
                selected[$idx]="true"
            fi
        fi
    done

    # Export results to global variables
    for i in "${!names[@]}"; do
        case "${names[$i]}" in
            images) PUBLISH_IMAGES="${selected[$i]}" ;;
            cli)    PUBLISH_CLI="${selected[$i]}" ;;
            fuse)   PUBLISH_FUSE="${selected[$i]}" ;;
        esac
    done
}

# --- Config Persistence ---
save_config() {
    mkdir -p "$CONFIG_DIR"
    chmod 700 "$CONFIG_DIR"

    cat > "$CONFIG_FILE" << EOF
# Publish Wizard Configuration
# Generated by publish-wizard.sh $WIZARD_VERSION on $(date -Iseconds)

DEFAULT_BUMP_TYPE="$BUMP_TYPE"
PUBLISH_IMAGES=$PUBLISH_IMAGES
PUBLISH_CLI=$PUBLISH_CLI
PUBLISH_FUSE=$PUBLISH_FUSE
USE_MULTI_ARCH=$USE_MULTI_ARCH
EOF

    chmod 600 "$CONFIG_FILE"
    log_success "Preferences saved to $CONFIG_FILE"
}

load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        # shellcheck disable=SC1090
        source "$CONFIG_FILE"
        return 0
    fi
    return 1
}

# ============================================================================
# SECTION 3: AUTH HELPERS
# ============================================================================

check_ghcr_auth() {
    if docker login ghcr.io --get-login &>/dev/null; then
        return 0
    fi
    if command -v gh &>/dev/null; then
        if gh auth token 2>/dev/null | docker login ghcr.io -u "$(gh api user -q .login 2>/dev/null)" --password-stdin &>/dev/null; then
            return 0
        fi
    fi
    return 1
}

check_npm_auth() {
    npm whoami &>/dev/null
}

check_pypi_auth() {
    [[ -f ~/.pypirc ]] || command -v twine &>/dev/null
}

verify_auth() {
    # Verify auth for a target, prompt to re-auth if needed
    # Usage: verify_auth ghcr|npm|pypi
    local target="$1"
    local check_fn="check_${target}_auth"
    local auth_cmd=""

    case "$target" in
        ghcr) auth_cmd="docker login ghcr.io" ;;
        npm)  auth_cmd="npm login" ;;
        pypi) auth_cmd="Configure ~/.pypirc or install twine" ;;
    esac

    if ! $check_fn; then
        log_warn "$target authentication expired or missing"
        echo -e "   Please run: ${BOLD}$auth_cmd${NC}"
        read -p "   Press Enter when ready..." </dev/tty

        if ! $check_fn; then
            log_error "Still not authenticated to $target"
            return 1
        fi
    fi

    log_success "$target authenticated"
    return 0
}

# ============================================================================
# SECTION 4: WIZARD STEPS
# ============================================================================

step_load_state() {
    log_step "Loading current state"

    # Get current versions from publish.sh status (parse output)
    CURRENT_VERSION=$(cat "$PROJECT_ROOT/VERSION" 2>/dev/null | tr -d '[:space:]')
    CLI_VERSION=$(node -p "require('$PROJECT_ROOT/cli/package.json').version" 2>/dev/null || echo "unknown")
    FUSE_VERSION=$(grep -E "^version" "$PROJECT_ROOT/fuse/pyproject.toml" 2>/dev/null | cut -d'"' -f2 || echo "unknown")

    # Get git state
    local latest_tag=$(git -C "$PROJECT_ROOT" describe --tags --abbrev=0 2>/dev/null || echo "none")
    if [[ "$latest_tag" != "none" ]]; then
        COMMITS_SINCE_TAG=$(git -C "$PROJECT_ROOT" rev-list "$latest_tag"..HEAD --count 2>/dev/null || echo "0")
    else
        COMMITS_SINCE_TAG=$(git -C "$PROJECT_ROOT" rev-list HEAD --count 2>/dev/null || echo "0")
    fi

    echo "  Platform version: ${BOLD}$CURRENT_VERSION${NC}"
    echo "  CLI version:      $CLI_VERSION"
    echo "  FUSE version:     $FUSE_VERSION"
    echo "  Commits since $latest_tag: ${YELLOW}$COMMITS_SINCE_TAG${NC}"
}

step_load_saved_config() {
    if load_config; then
        log_step "Previous settings found"
        echo "  Bump type: $DEFAULT_BUMP_TYPE"
        echo "  Images:    $PUBLISH_IMAGES"
        echo "  CLI:       $PUBLISH_CLI"
        echo "  FUSE:      $PUBLISH_FUSE"
        echo "  Multi-arch: $USE_MULTI_ARCH"

        if prompt_bool "Use these settings?" "y"; then
            BUMP_TYPE="$DEFAULT_BUMP_TYPE"
            return 0
        fi
    fi
    return 1
}

step_select_version() {
    log_step "Version Selection"

    # Calculate what each bump would produce
    IFS='.' read -r major minor patch <<< "${CURRENT_VERSION%-*}"
    patch=${patch:-0}

    local patch_ver="$major.$minor.$((patch + 1))"
    local minor_ver="$major.$((minor + 1)).0"
    local major_ver="$((major + 1)).0.0"

    echo "  Current version: ${BOLD}$CURRENT_VERSION${NC}"
    echo ""

    local choice=$(prompt_select "Select version bump:" \
        "patch → $patch_ver" \
        "minor → $minor_ver" \
        "major → $major_ver")

    case "$choice" in
        patch*) BUMP_TYPE="patch"; NEW_VERSION="$patch_ver" ;;
        minor*) BUMP_TYPE="minor"; NEW_VERSION="$minor_ver" ;;
        major*) BUMP_TYPE="major"; NEW_VERSION="$major_ver" ;;
    esac

    log_success "Will bump to ${BOLD}$NEW_VERSION${NC}"
}

step_enter_message() {
    log_step "Release Message"

    local choice=$(prompt_select "How would you like to enter the release message?" \
        "Type message now" \
        "Load from file" \
        "Open in \$EDITOR")

    case "$choice" in
        "Type message now")
            echo -e "\n${DIM}Enter your release message (press Ctrl+D when done):${NC}" >&2
            RELEASE_MESSAGE=$(cat </dev/tty)
            ;;
        "Load from file")
            local filepath=$(prompt_value "Enter file path")
            if [[ -f "$filepath" ]]; then
                RELEASE_MESSAGE=$(cat "$filepath")
            else
                log_error "File not found: $filepath"
                return 1
            fi
            ;;
        "Open in \$EDITOR")
            local tmpfile=$(mktemp)
            ${EDITOR:-nano} "$tmpfile" </dev/tty >/dev/tty
            RELEASE_MESSAGE=$(cat "$tmpfile")
            rm -f "$tmpfile"
            ;;
    esac

    local char_count=${#RELEASE_MESSAGE}
    log_success "Message entered ($char_count characters)"
}

step_select_artifacts() {
    log_step "Artifact Selection"

    # Show current publish status
    echo "  ${DIM}(Artifacts already at latest version are pre-deselected)${NC}"
    echo ""

    prompt_multiselect \
        "images|$PUBLISH_IMAGES" \
        "cli|$PUBLISH_CLI" \
        "fuse|$PUBLISH_FUSE"

    if [[ "$PUBLISH_IMAGES" == "true" ]]; then
        if prompt_bool "Build multi-arch (amd64 + arm64)?" "y"; then
            USE_MULTI_ARCH=true
        else
            USE_MULTI_ARCH=false
        fi
    fi
}

step_show_summary() {
    log_step "Summary"

    echo ""
    echo -e "  ${BOLD}Version:${NC}    $CURRENT_VERSION → ${GREEN}$NEW_VERSION${NC} ($BUMP_TYPE)"
    echo -e "  ${BOLD}Message:${NC}    ${DIM}$(echo "$RELEASE_MESSAGE" | head -1 | cut -c1-50)...${NC}"
    echo -e "  ${BOLD}Artifacts:${NC}"
    [[ "$PUBLISH_IMAGES" == "true" ]] && echo "              • Images (api, web, operator) $([ "$USE_MULTI_ARCH" == "true" ] && echo "[amd64+arm64]" || echo "[host arch]")"
    [[ "$PUBLISH_CLI" == "true" ]]    && echo "              • CLI (npm)"
    [[ "$PUBLISH_FUSE" == "true" ]]   && echo "              • FUSE (pypi)"
    echo ""
    echo -e "  ${BOLD}Actions:${NC}"
    echo "    1. Bump VERSION file"
    echo "    2. Sync script versions"
    echo "    3. Commit and tag v$NEW_VERSION"
    echo "    4. Push to origin"
    [[ "$PUBLISH_IMAGES" == "true" ]] && echo "    5. Build and push images"
    [[ "$PUBLISH_CLI" == "true" ]]    && echo "    6. Build and publish CLI"
    [[ "$PUBLISH_FUSE" == "true" ]]   && echo "    7. Build and publish FUSE"
    echo ""
}

step_confirm() {
    if ! prompt_bool "Proceed with release?" "y"; then
        log_warn "Aborted by user"
        exit 0
    fi
}

step_execute() {
    log_step "Executing Release"

    # 1. Run release (bump, sync, commit, tag)
    echo ""
    log_info "Running: publish.sh release $BUMP_TYPE"
    "$PUBLISH_SH" release "$BUMP_TYPE" -m "$RELEASE_MESSAGE"

    # 2. Push to origin
    echo ""
    log_info "Pushing to origin..."
    local branch=$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD)
    git -C "$PROJECT_ROOT" push origin "$branch" --tags
    log_success "Pushed to origin/$branch"

    # 3. Build and push artifacts
    if [[ "$PUBLISH_IMAGES" == "true" ]]; then
        echo ""
        log_info "Building and pushing images..."
        verify_auth ghcr || exit 1

        local arch_flag=""
        [[ "$USE_MULTI_ARCH" == "true" ]] && arch_flag="--multi-arch"
        "$PUBLISH_SH" images $arch_flag
    fi

    if [[ "$PUBLISH_CLI" == "true" ]]; then
        echo ""
        log_info "Publishing CLI to npm..."
        verify_auth npm || exit 1
        "$PUBLISH_SH" cli
    fi

    if [[ "$PUBLISH_FUSE" == "true" ]]; then
        echo ""
        log_info "Publishing FUSE to PyPI..."
        verify_auth pypi || exit 1
        "$PUBLISH_SH" fuse
    fi

    echo ""
    log_success "Release $NEW_VERSION complete!"
}

step_save_preferences() {
    echo ""
    if prompt_bool "Save these preferences for next time?" "y"; then
        save_config
    fi
}

# ============================================================================
# SECTION 5: MAIN
# ============================================================================

show_help() {
    cat << 'EOF'
Usage: publish-wizard.sh [options]

Interactive release wizard for Knowledge Graph System.

Options:
  --reset    Clear saved preferences
  --help     Show this help

The wizard will guide you through:
  1. Selecting version bump (patch/minor/major)
  2. Entering release message
  3. Choosing artifacts to publish
  4. Confirming and executing the release

All actual operations are performed by publish.sh.
EOF
}

main() {
    # Parse arguments
    case "${1:-}" in
        --help|-h)
            show_help
            exit 0
            ;;
        --reset)
            rm -f "$CONFIG_FILE"
            log_success "Preferences cleared"
            exit 0
            ;;
    esac

    # Header
    echo ""
    echo -e "${BOLD}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║          Knowledge Graph Release Wizard v$WIZARD_VERSION            ║${NC}"
    echo -e "${BOLD}╚════════════════════════════════════════════════════════════╝${NC}"

    # Run wizard steps
    step_load_state

    if ! step_load_saved_config; then
        step_select_version
        step_enter_message
        step_select_artifacts
    else
        # Using saved config - just need message
        # Calculate NEW_VERSION from BUMP_TYPE
        IFS='.' read -r major minor patch <<< "${CURRENT_VERSION%-*}"
        patch=${patch:-0}
        case "$BUMP_TYPE" in
            patch) NEW_VERSION="$major.$minor.$((patch + 1))" ;;
            minor) NEW_VERSION="$major.$((minor + 1)).0" ;;
            major) NEW_VERSION="$((major + 1)).0.0" ;;
        esac
        step_enter_message
    fi

    step_show_summary
    step_confirm
    step_execute
    step_save_preferences

    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  Release v$NEW_VERSION published successfully!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

main "$@"
