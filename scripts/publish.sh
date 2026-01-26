#!/bin/bash
# ============================================================================
# publish.sh - Unified publishing and versioning tool for Knowledge Graph System
#
# Manages:
#   - Version bumping (platform, scripts, packages)
#   - Docker images (api, web, operator) → GitHub Container Registry
#   - npm package (CLI/MCP)              → npm registry
#   - Python package (FUSE)              → PyPI
#
# Usage:
#   ./scripts/publish.sh status                  # Show all versions
#   ./scripts/publish.sh bump patch              # Bump platform version
#   ./scripts/publish.sh bump cli patch          # Bump CLI version
#   ./scripts/publish.sh sync-scripts            # Update script versions
#   ./scripts/publish.sh release patch -m "msg"  # Full release workflow
#   ./scripts/publish.sh images [api|web]        # Publish Docker images
#   ./scripts/publish.sh cli                     # Publish npm package
#   ./scripts/publish.sh fuse                    # Publish PyPI package
#
# Options:
#   -m, --message "desc"   Description for release
#   --dry-run              Preview without making changes
#   --skip-build           Skip build step
#
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# Resolve symlinks to get actual script location
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Registries
GHCR_REGISTRY="ghcr.io"
IMAGE_PREFIX="aaronsb/knowledge-graph-system"

# ============================================================================
# Parse arguments
# ============================================================================

DRY_RUN=false
SKIP_BUILD=false
FORCE=false
USE_TESTPYPI=false
DESCRIPTION=""
COMMAND=""
BUMP_TYPE=""
BUMP_TARGET="platform"
TARGETS=()

show_help() {
    cat << 'EOF'
Usage: publish.sh <command> [options]

Version Management:
  status                    Show all versions and auth status
  bump <type> [target]      Bump version (type: major|minor|patch)
                            target: platform (default), cli, fuse
  sync-scripts              Update script versions to match VERSION file
  release <type> -m "msg"   Full release: bump, sync, tag, publish

Publishing:
  images [api|web|operator] Publish Docker images to GHCR
  cli                       Publish npm package (@aaronsb/kg-cli)
  fuse                      Publish Python package (kg-fuse) to PyPI
  all                       Publish everything (images, cli, fuse)

Options:
  -m, --message "desc"      Description for release/publish
  --dry-run                 Build locally but don't push to registries
  --skip-build              Skip build step (push existing images only)
  --force                   Bypass "already published" checks
  --test                    Use TestPyPI instead of PyPI (fuse only)
  -h, --help                Show this help

Examples:
  publish.sh status
  publish.sh bump patch                    # 0.6.5 → 0.6.6
  publish.sh bump cli minor                # CLI 0.6.6 → 0.7.0
  publish.sh release patch -m "Bug fixes"  # Full release workflow
  publish.sh images -m "API improvements"
  publish.sh all -m "Release v0.7.0"
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        status|bump|sync-scripts|release|images|cli|fuse|all)
            COMMAND="$1"
            shift
            ;;
        major|minor|patch)
            BUMP_TYPE="$1"
            shift
            ;;
        platform|cli|fuse)
            if [ "$COMMAND" = "bump" ]; then
                BUMP_TARGET="$1"
            else
                TARGETS+=("$1")
            fi
            shift
            ;;
        api|web|operator)
            TARGETS+=("$1")
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --test)
            USE_TESTPYPI=true
            shift
            ;;
        -m|--message)
            DESCRIPTION="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            echo "Run '$0 --help' for usage"
            exit 1
            ;;
    esac
done

if [ -z "$COMMAND" ]; then
    echo -e "${RED}No command specified${NC}"
    echo "Run '$0 --help' for usage"
    exit 1
fi

# ============================================================================
# Version reading
# ============================================================================

get_versions() {
    VERSION=$(cat "$PROJECT_ROOT/VERSION" 2>/dev/null | tr -d '[:space:]' || echo "0.0.0")
    GIT_SHA=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")
    GIT_BRANCH=$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
    BUILD_DATE=$(date -Iseconds)

    # Package versions
    CLI_VERSION=$(node -p "require('$PROJECT_ROOT/cli/package.json').version" 2>/dev/null || echo "unknown")
    FUSE_VERSION=$(grep -E "^version" "$PROJECT_ROOT/fuse/pyproject.toml" 2>/dev/null | cut -d'"' -f2 || echo "unknown")

    # Script versions (embedded) - match only static definitions like VAR="x.y.z"
    INSTALL_VERSION=$(grep -E '^INSTALLER_VERSION="[0-9]' "$PROJECT_ROOT/install.sh" 2>/dev/null | head -1 | cut -d'"' -f2 || echo "unknown")
    OPERATOR_VERSION=$(grep -E '^OPERATOR_VERSION="[0-9]' "$PROJECT_ROOT/operator.sh" 2>/dev/null | head -1 | cut -d'"' -f2 || echo "unknown")
    CLIENT_MGR_VERSION=$(grep -E '^CLIENT_MANAGER_VERSION="[0-9]' "$PROJECT_ROOT/client-manager.sh" 2>/dev/null | head -1 | cut -d'"' -f2 || echo "unknown")

    # Git tag info for smart publish checks
    LATEST_TAG=$(git -C "$PROJECT_ROOT" describe --tags --abbrev=0 2>/dev/null || echo "")
    if [ -n "$LATEST_TAG" ]; then
        COMMITS_SINCE_TAG=$(git -C "$PROJECT_ROOT" rev-list "$LATEST_TAG"..HEAD --count 2>/dev/null || echo "0")
    else
        COMMITS_SINCE_TAG=$(git -C "$PROJECT_ROOT" rev-list HEAD --count 2>/dev/null || echo "0")
    fi
}

# Check if version is already published
is_version_published() {
    local target="$1"
    local version="$2"

    case "$target" in
        images)
            # Check GHCR using docker manifest inspect (respects auth)
            docker manifest inspect "$GHCR_REGISTRY/$IMAGE_PREFIX/kg-api:$version" &>/dev/null
            return $?
            ;;
        cli)
            npm view "@aaronsb/kg-cli@$version" version &>/dev/null
            return $?
            ;;
        fuse)
            # Try pip index first (pip 21.2+), fall back to pip show with version check
            if pip index versions kg-fuse 2>/dev/null | grep -q "$version"; then
                return 0
            fi
            # Fallback: check if installed version matches (less reliable)
            pip show kg-fuse 2>/dev/null | grep -q "Version: $version"
            return $?
            ;;
    esac
    return 1
}

# Smart pre-publish check
check_publish_needed() {
    local target="$1"
    local version="$2"
    local force="${3:-false}"

    if [ "$force" = "true" ]; then
        return 0
    fi

    # Check if already published
    if is_version_published "$target" "$version"; then
        echo -e "${YELLOW}⚠ $target v$version already published${NC}"
        if [ "$COMMITS_SINCE_TAG" -gt 0 ]; then
            echo -e "  ${DIM}$COMMITS_SINCE_TAG commit(s) since last tag ($LATEST_TAG)${NC}"
            echo -e "  ${DIM}Run: ./scripts/publish.sh release patch -m \"description\"${NC}"
        else
            echo -e "  ${DIM}No new commits. Nothing to publish.${NC}"
        fi
        return 1
    fi

    return 0
}

# ============================================================================
# Version bumping
# ============================================================================

bump_version() {
    local current="$1"
    local type="$2"

    IFS='.' read -r major minor patch <<< "${current%-*}"  # Strip any -dev suffix
    patch=${patch:-0}

    case "$type" in
        major) echo "$((major + 1)).0.0" ;;
        minor) echo "$major.$((minor + 1)).0" ;;
        patch) echo "$major.$minor.$((patch + 1))" ;;
        *) echo "$current" ;;
    esac
}

update_version_file() {
    local new_version="$1"
    if [ "$DRY_RUN" = "true" ]; then
        echo -e "${DIM}Would update VERSION to $new_version${NC}"
    else
        echo "$new_version" > "$PROJECT_ROOT/VERSION"
        echo -e "${GREEN}✓ Updated VERSION to $new_version${NC}"
    fi
}

update_script_version() {
    local file="$1"
    local var_name="$2"
    local new_version="$3"

    if [ ! -f "$file" ]; then
        echo -e "${YELLOW}⚠ $file not found${NC}"
        return 1
    fi

    local file_basename=$(basename "$file")
    if [ "$DRY_RUN" = "true" ]; then
        echo -e "${DIM}Would update $file_basename $var_name to $new_version${NC}"
    else
        sed -i "s/^${var_name}=\"[^\"]*\"/${var_name}=\"${new_version}\"/" "$file"
        # Verify the update succeeded
        if grep -q "^${var_name}=\"${new_version}\"" "$file"; then
            echo -e "${GREEN}✓ Updated $file_basename to $new_version${NC}"
        else
            echo -e "${RED}✗ Failed to update $file_basename${NC}"
            return 1
        fi
    fi
}

update_cli_version() {
    local new_version="$1"
    local package_json="$PROJECT_ROOT/cli/package.json"

    if [ ! -f "$package_json" ]; then
        echo -e "${RED}✗ cli/package.json not found${NC}"
        return 1
    fi

    if [ "$DRY_RUN" = "true" ]; then
        echo -e "${DIM}Would update cli/package.json to $new_version${NC}"
    else
        # Use node to update package.json properly
        node -e "
            const fs = require('fs');
            const pkg = JSON.parse(fs.readFileSync('$package_json'));
            pkg.version = '$new_version';
            fs.writeFileSync('$package_json', JSON.stringify(pkg, null, 2) + '\n');
        "
        echo -e "${GREEN}✓ Updated cli/package.json to $new_version${NC}"
    fi
}

update_fuse_version() {
    local new_version="$1"
    local pyproject="$PROJECT_ROOT/fuse/pyproject.toml"

    if [ ! -f "$pyproject" ]; then
        echo -e "${RED}✗ fuse/pyproject.toml not found${NC}"
        return 1
    fi

    if [ "$DRY_RUN" = "true" ]; then
        echo -e "${DIM}Would update fuse/pyproject.toml to $new_version${NC}"
    else
        sed -i "s/^version = \"[^\"]*\"/version = \"$new_version\"/" "$pyproject"
        # Verify the update succeeded
        if grep -q "^version = \"$new_version\"" "$pyproject"; then
            echo -e "${GREEN}✓ Updated fuse/pyproject.toml to $new_version${NC}"
        else
            echo -e "${RED}✗ Failed to update fuse/pyproject.toml${NC}"
            return 1
        fi
    fi
}

# ============================================================================
# Authentication checks
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
    command -v twine &>/dev/null
}

# ============================================================================
# Commands
# ============================================================================

cmd_status() {
    get_versions

    echo -e "${BOLD}Knowledge Graph System - Version Status${NC}"
    echo ""

    echo -e "${CYAN}Platform:${NC}"
    echo "  VERSION file:     $VERSION"
    echo "  Git commit:       $GIT_SHA"
    echo "  Git branch:       $GIT_BRANCH"
    if [ -n "$LATEST_TAG" ]; then
        if [ "$COMMITS_SINCE_TAG" -gt 0 ]; then
            echo -e "  Latest tag:       $LATEST_TAG ${YELLOW}(+$COMMITS_SINCE_TAG commits)${NC}"
        else
            echo -e "  Latest tag:       $LATEST_TAG ${GREEN}(current)${NC}"
        fi
    else
        echo -e "  Latest tag:       ${DIM}none${NC}"
    fi
    echo ""

    echo -e "${CYAN}Scripts (embedded versions):${NC}"
    local scripts_match=true
    if [ "$INSTALL_VERSION" != "$VERSION" ]; then
        echo -e "  install.sh:       ${YELLOW}$INSTALL_VERSION${NC} (differs from VERSION)"
        scripts_match=false
    else
        echo -e "  install.sh:       ${GREEN}$INSTALL_VERSION${NC}"
    fi
    if [ "$OPERATOR_VERSION" != "$VERSION" ]; then
        echo -e "  operator.sh:      ${YELLOW}$OPERATOR_VERSION${NC} (differs from VERSION)"
        scripts_match=false
    else
        echo -e "  operator.sh:      ${GREEN}$OPERATOR_VERSION${NC}"
    fi
    if [ "$CLIENT_MGR_VERSION" != "$VERSION" ]; then
        echo -e "  client-manager:   ${YELLOW}$CLIENT_MGR_VERSION${NC} (differs from VERSION)"
        scripts_match=false
    else
        echo -e "  client-manager:   ${GREEN}$CLIENT_MGR_VERSION${NC}"
    fi
    if [ "$scripts_match" = "false" ]; then
        echo -e "  ${DIM}Run 'publish.sh sync-scripts' to update${NC}"
    fi
    echo ""

    echo -e "${CYAN}Packages (independent versions):${NC}"
    echo "  CLI (npm):        $CLI_VERSION"
    echo "  FUSE (PyPI):      $FUSE_VERSION"
    echo ""

    echo -e "${CYAN}Registry Authentication:${NC}"
    if check_ghcr_auth; then
        echo -e "  GHCR:   ${GREEN}✓ authenticated${NC}"
    else
        echo -e "  GHCR:   ${RED}✗ not logged in${NC}"
    fi
    if check_npm_auth; then
        echo -e "  npm:    ${GREEN}✓ authenticated${NC} ($(npm whoami 2>/dev/null))"
    else
        echo -e "  npm:    ${RED}✗ not logged in${NC}"
    fi
    if check_pypi_auth; then
        echo -e "  PyPI:   ${GREEN}✓ twine available${NC}"
    else
        echo -e "  PyPI:   ${RED}✗ twine not found${NC}"
    fi
    echo ""

    echo -e "${CYAN}Published versions:${NC}"
    local npm_pub=$(npm view @aaronsb/kg-cli version 2>/dev/null || echo "not published")
    local pypi_pub=$(pip index versions kg-fuse 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "not published")
    echo "  npm (@aaronsb/kg-cli):  $npm_pub"
    echo "  PyPI (kg-fuse):         $pypi_pub"
    echo ""

    # Publish readiness summary
    echo -e "${CYAN}Publish Readiness:${NC}"

    if is_version_published "cli" "$CLI_VERSION" 2>/dev/null; then
        echo -e "  CLI:    ${GREEN}✓ v$CLI_VERSION published${NC}"
    else
        echo -e "  CLI:    ${BLUE}○ v$CLI_VERSION ready to publish${NC}"
    fi

    if is_version_published "fuse" "$FUSE_VERSION" 2>/dev/null; then
        echo -e "  FUSE:   ${GREEN}✓ v$FUSE_VERSION published${NC}"
    else
        echo -e "  FUSE:   ${BLUE}○ v$FUSE_VERSION ready to publish${NC}"
    fi

    # Check if current VERSION tag exists (images use platform version)
    if is_version_published "images" "$VERSION" 2>/dev/null; then
        echo -e "  Images: ${GREEN}✓ v$VERSION published${NC}"
    else
        echo -e "  Images: ${BLUE}○ v$VERSION ready to publish${NC}"
    fi

    echo ""

    # Recommendations
    if [ "$COMMITS_SINCE_TAG" -gt 0 ]; then
        echo -e "${CYAN}Recommendation:${NC}"
        echo -e "  $COMMITS_SINCE_TAG commit(s) since $LATEST_TAG"
        echo -e "  → ${BOLD}./publish.sh release patch -m \"description\"${NC}"
        echo ""
    fi
}

cmd_bump() {
    if [ -z "$BUMP_TYPE" ]; then
        echo -e "${RED}Bump type required: major, minor, or patch${NC}"
        exit 1
    fi

    get_versions

    case "$BUMP_TARGET" in
        platform)
            local new_version=$(bump_version "$VERSION" "$BUMP_TYPE")
            echo -e "${BOLD}Bumping platform version${NC}"
            echo "  Current: $VERSION"
            echo "  New:     $new_version"
            echo ""
            update_version_file "$new_version"
            ;;
        cli)
            local new_version=$(bump_version "$CLI_VERSION" "$BUMP_TYPE")
            echo -e "${BOLD}Bumping CLI version${NC}"
            echo "  Current: $CLI_VERSION"
            echo "  New:     $new_version"
            echo ""
            update_cli_version "$new_version"
            ;;
        fuse)
            local new_version=$(bump_version "$FUSE_VERSION" "$BUMP_TYPE")
            echo -e "${BOLD}Bumping FUSE version${NC}"
            echo "  Current: $FUSE_VERSION"
            echo "  New:     $new_version"
            echo ""
            update_fuse_version "$new_version"
            ;;
    esac
}

cmd_sync_scripts() {
    get_versions

    echo -e "${BOLD}Syncing script versions to $VERSION${NC}"
    echo ""

    update_script_version "$PROJECT_ROOT/install.sh" "INSTALLER_VERSION" "$VERSION"
    update_script_version "$PROJECT_ROOT/operator.sh" "OPERATOR_VERSION" "$VERSION"
    update_script_version "$PROJECT_ROOT/client-manager.sh" "CLIENT_MANAGER_VERSION" "$VERSION"
}

cmd_release() {
    if [ -z "$BUMP_TYPE" ]; then
        echo -e "${RED}Release requires bump type: major, minor, or patch${NC}"
        echo "Usage: publish.sh release <patch|minor|major> -m \"message\""
        exit 1
    fi

    get_versions
    local new_version=$(bump_version "$VERSION" "$BUMP_TYPE")

    echo -e "${BOLD}Release workflow: $VERSION → $new_version${NC}"
    [ -n "$DESCRIPTION" ] && echo -e "  Message: $DESCRIPTION"
    [ "$DRY_RUN" = "true" ] && echo -e "  ${YELLOW}DRY RUN MODE${NC}"
    echo ""

    # Step 1: Bump VERSION
    echo -e "${CYAN}Step 1: Bump version${NC}"
    update_version_file "$new_version"
    VERSION="$new_version"  # Update for subsequent steps

    # Step 2: Sync scripts
    echo ""
    echo -e "${CYAN}Step 2: Sync script versions${NC}"
    update_script_version "$PROJECT_ROOT/install.sh" "INSTALLER_VERSION" "$VERSION"
    update_script_version "$PROJECT_ROOT/operator.sh" "OPERATOR_VERSION" "$VERSION"
    update_script_version "$PROJECT_ROOT/client-manager.sh" "CLIENT_MANAGER_VERSION" "$VERSION"

    # Step 3: Commit and tag
    echo ""
    echo -e "${CYAN}Step 3: Commit and tag${NC}"
    if [ "$DRY_RUN" = "true" ]; then
        echo -e "${DIM}Would commit: 'Release v$VERSION'${NC}"
        echo -e "${DIM}Would tag: v$VERSION${NC}"
    else
        git -C "$PROJECT_ROOT" add VERSION install.sh operator.sh client-manager.sh
        local commit_msg="Release v$VERSION"
        [ -n "$DESCRIPTION" ] && commit_msg="$commit_msg: $DESCRIPTION"
        git -C "$PROJECT_ROOT" commit -m "$commit_msg"
        git -C "$PROJECT_ROOT" tag -a "v$VERSION" -m "$commit_msg"
        echo -e "${GREEN}✓ Committed and tagged v$VERSION${NC}"
    fi

    # Step 4: Instructions
    echo ""
    echo -e "${CYAN}Next steps:${NC}"
    local current_branch=$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
    echo "  1. Push: git push origin $current_branch --tags"
    echo "  2. Publish images: ./publish.sh images"
    echo "  3. Publish CLI (if needed): ./publish.sh cli"
    echo "  4. Publish FUSE (if needed): ./publish.sh fuse"
    echo ""
}

cmd_images() {
    get_versions

    if [ ${#TARGETS[@]} -eq 0 ]; then
        TARGETS=(api web operator)
    fi

    echo -e "${BOLD}Publishing Docker images to GHCR${NC}"
    echo -e "  Version: ${BLUE}$VERSION${NC}"
    echo -e "  Commit:  ${BLUE}$GIT_SHA${NC}"
    echo -e "  Targets: ${BLUE}${TARGETS[*]}${NC}"
    [ -n "$DESCRIPTION" ] && echo -e "  Message: ${BLUE}$DESCRIPTION${NC}"
    [ "$DRY_RUN" = "true" ] && echo -e "  Mode:    ${YELLOW}DRY RUN${NC}"
    echo ""

    # Smart check: is this version already published?
    if [ "$DRY_RUN" = "false" ] && ! check_publish_needed "images" "$VERSION" "$FORCE"; then
        exit 0
    fi

    if [ "$DRY_RUN" = "false" ] && ! check_ghcr_auth; then
        echo -e "${RED}Not authenticated to GHCR${NC}"
        echo "Run: docker login ghcr.io"
        exit 1
    fi

    cd "$PROJECT_ROOT"

    for target in "${TARGETS[@]}"; do
        local context dockerfile image_name

        case "$target" in
            api)
                context="."
                dockerfile="./api/Dockerfile"
                image_name="kg-api"
                ;;
            web)
                context="./web"
                dockerfile="./web/Dockerfile"
                image_name="kg-web"
                ;;
            operator)
                context="."
                dockerfile="./operator/Dockerfile"
                image_name="kg-operator"
                ;;
            *)
                echo -e "${RED}Unknown target: $target${NC}"
                continue
                ;;
        esac

        local full_image="$GHCR_REGISTRY/$IMAGE_PREFIX/$image_name"

        if [ "$SKIP_BUILD" = "false" ]; then
            echo -e "${BLUE}→ Building $target...${NC}"

            local label_args=(
                --label "org.opencontainers.image.version=$VERSION"
                --label "org.opencontainers.image.revision=$GIT_SHA"
                --label "org.opencontainers.image.created=$BUILD_DATE"
                --label "org.opencontainers.image.source=https://github.com/$IMAGE_PREFIX"
            )
            [ -n "$DESCRIPTION" ] && label_args+=(--label "org.opencontainers.image.description=$DESCRIPTION")

            docker build \
                --file "$dockerfile" \
                --build-arg GIT_COMMIT="$GIT_SHA" \
                --build-arg BUILD_DATE="$BUILD_DATE" \
                "${label_args[@]}" \
                --tag "$full_image:latest" \
                --tag "$full_image:$VERSION" \
                --tag "$full_image:sha-$GIT_SHA" \
                "$context"

            echo -e "${GREEN}✓ Built $full_image${NC}"
        fi

        if [ "$DRY_RUN" = "false" ]; then
            echo -e "${BLUE}→ Pushing $target...${NC}"
            docker push "$full_image:latest"
            docker push "$full_image:$VERSION"
            docker push "$full_image:sha-$GIT_SHA"
            echo -e "${GREEN}✓ Pushed $full_image:$VERSION${NC}"
        fi
        echo ""
    done
}

cmd_cli() {
    get_versions

    echo -e "${BOLD}Publishing CLI to npm${NC}"
    echo -e "  Version: ${BLUE}$CLI_VERSION${NC}"
    [ "$DRY_RUN" = "true" ] && echo -e "  Mode:    ${YELLOW}DRY RUN${NC}"
    echo ""

    # Smart check: is this version already published?
    if [ "$DRY_RUN" = "false" ] && ! check_publish_needed "cli" "$CLI_VERSION" "$FORCE"; then
        echo -e "  ${DIM}Bump first: ./scripts/publish.sh bump cli patch${NC}"
        exit 0
    fi

    if [ "$DRY_RUN" = "false" ] && ! check_npm_auth; then
        echo -e "${RED}Not authenticated to npm${NC}"
        echo "Run: npm login"
        exit 1
    fi

    cd "$PROJECT_ROOT/cli"

    if [ "$SKIP_BUILD" = "false" ]; then
        echo -e "${BLUE}→ Building CLI...${NC}"
        npm run clean
        npm run build
        echo -e "${GREEN}✓ Build complete${NC}"
    fi

    echo ""
    if [ "$DRY_RUN" = "false" ]; then
        echo -e "${BLUE}→ Publishing to npm...${NC}"
        npm publish --access public
        echo -e "${GREEN}✓ Published @aaronsb/kg-cli@$CLI_VERSION${NC}"
    fi
}

cmd_fuse() {
    get_versions

    local registry="PyPI"
    local twine_repo=""
    if [ "$USE_TESTPYPI" = "true" ]; then
        registry="TestPyPI"
        twine_repo="--repository testpypi"
    fi

    echo -e "${BOLD}Publishing FUSE driver to $registry${NC}"
    echo -e "  Version: ${BLUE}$FUSE_VERSION${NC}"
    [ "$USE_TESTPYPI" = "true" ] && echo -e "  Registry: ${YELLOW}TestPyPI (test.pypi.org)${NC}"
    [ "$DRY_RUN" = "true" ] && echo -e "  Mode:    ${YELLOW}DRY RUN${NC}"
    echo ""

    # Smart check: skip for testpypi (versions can be reused for testing)
    if [ "$DRY_RUN" = "false" ] && [ "$USE_TESTPYPI" = "false" ]; then
        if ! check_publish_needed "fuse" "$FUSE_VERSION" "$FORCE"; then
            echo -e "  ${DIM}Bump first: ./publish.sh bump fuse patch${NC}"
            exit 0
        fi
    fi

    if ! command -v twine &>/dev/null; then
        echo -e "${RED}twine not found${NC}"
        echo "Run: pip install twine build"
        exit 1
    fi

    cd "$PROJECT_ROOT/fuse"

    if [ "$SKIP_BUILD" = "false" ]; then
        echo -e "${BLUE}→ Building package...${NC}"
        rm -rf dist/ build/ *.egg-info/
        python -m build 2>/dev/null || { pip install build && python -m build; }
        echo -e "${GREEN}✓ Build complete${NC}"
    fi

    echo ""
    if [ "$DRY_RUN" = "false" ]; then
        echo -e "${BLUE}→ Uploading to $registry...${NC}"
        twine upload $twine_repo dist/*
        echo -e "${GREEN}✓ Published kg-fuse==$FUSE_VERSION to $registry${NC}"
        if [ "$USE_TESTPYPI" = "true" ]; then
            echo -e "  ${DIM}Install with: pip install -i https://test.pypi.org/simple/ kg-fuse${NC}"
        fi
    fi
}

cmd_all() {
    echo -e "${BOLD}Publishing all packages${NC}"
    echo ""
    cmd_images
    cmd_cli
    cmd_fuse
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ All packages published${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# ============================================================================
# Main
# ============================================================================

case "$COMMAND" in
    status)       cmd_status ;;
    bump)         cmd_bump ;;
    sync-scripts) cmd_sync_scripts ;;
    release)      cmd_release ;;
    images)       cmd_images ;;
    cli)          cmd_cli ;;
    fuse)         cmd_fuse ;;
    all)          cmd_all ;;
esac
