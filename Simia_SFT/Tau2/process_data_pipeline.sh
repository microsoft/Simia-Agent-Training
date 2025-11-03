#!/bin/bash



set -e  


RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color


log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}


if [ $# -lt 1 ]; then
    echo "Usage: $0 <input_file> [output_file]"
    echo "Example: $0 /path/to/input.json"
    echo "Example: $0 /path/to/input.json /path/to/output.json"
    exit 1
fi

INPUT_FILE="$1"
OUTPUT_FILE="$2"


if [ ! -f "$INPUT_FILE" ]; then
    log_error "Input file does not exist: $INPUT_FILE"
    exit 1
fi


if [ -z "$OUTPUT_FILE" ]; then
    DIR=$(dirname "$INPUT_FILE")
    BASENAME=$(basename "$INPUT_FILE" .json)
    OUTPUT_FILE="$DIR/${BASENAME}_processed.json"
fi


INPUT_FILE=$(realpath "$INPUT_FILE")
OUTPUT_FILE=$(realpath "$OUTPUT_FILE")

log_info "Starting data processing pipeline..."
log_info "Input file: $INPUT_FILE"
log_info "Output file: $OUTPUT_FILE"


SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_PATH/../.." && pwd)"
SCRIPT_DIR="$REPO_ROOT/Simia_SFT/Tau2"



SCRIPTS=(
    "$SCRIPT_DIR/fix_arguments.py"
    "$SCRIPT_DIR/tool2hermes.py"
    "$SCRIPT_DIR/tool_correct.py"
    "$SCRIPT_DIR/remove_think_tag.py"
    "    "$SCRIPT_DIR/replace_system_prompt_Hermes.py"
)

# Validate all scripts exist
for script in "${SCRIPTS[@]}"; do
    if [ ! -f "$script" ]; then
        log_error "Processing script does not exist: $script"
        exit 1
    fi
done

# Check config file (optional)
if [ ! -f "$CONFIG_FILE" ]; then
    log_warning "Config file does not exist: $CONFIG_FILE, will try to use default config"
fi

# Store intermediate file paths
INTERMEDIATE_FILES=()"
)


for script in "${SCRIPTS[@]}"; do
    if [ ! -f "$script" ]; then
        log_error "Processing script does not exist: $script"
        exit 1
    fi
done


if [ ! -f "$CONFIG_FILE" ]; then
    log_warning "Config file does not exist: $CONFIG_FILE, will try to use default config"
fi


INTERMEDIATE_FILES=()


cleanup() {
    if [ ${#INTERMEDIATE_FILES[@]} -gt 0 ]; then
        log_info "Cleaning up intermediate files..."
        for file in "${INTERMEDIATE_FILES[@]}"; do
            if [ -f "$file" ]; then
                rm -f "$file"
                log_success "Deleted intermediate file: $file"
            fi
        done
    fi
}


trap cleanup EXIT


CURRENT_INPUT="$INPUT_FILE"


for i in "${!SCRIPTS[@]}"; do
    STEP=$((i + 1))
    SCRIPT="${SCRIPTS[$i]}"
    SCRIPT_NAME=$(basename "$SCRIPT")
    
    log_info "========================================="
    log_info "Step $STEP/${#SCRIPTS[@]}: $SCRIPT_NAME"
    log_info "========================================="
    

    if [ $STEP -eq ${#SCRIPTS[@]} ]; then
        CURRENT_OUTPUT="$OUTPUT_FILE"
    else
        DIR=$(dirname "$INPUT_FILE")
        BASENAME=$(basename "$INPUT_FILE" .json)
        CURRENT_OUTPUT="$DIR/${BASENAME}_step${STEP}.json"
        INTERMEDIATE_FILES+=("$CURRENT_OUTPUT")
    fi
    
    log_info "Input: $CURRENT_INPUT"
    log_info "Output: $CURRENT_OUTPUT"
    
    case "$SCRIPT_NAME" in
        "fix_arguments_only.py")
            python3 "$SCRIPT" "$CURRENT_INPUT" "$CURRENT_OUTPUT"
            ;;
        "tool2hermes.py")
            python3 "$SCRIPT" --input "$CURRENT_INPUT" --output "$CURRENT_OUTPUT"
            ;;
        "tool_use_correct_v6.py")
            if [ -f "$CONFIG_FILE" ]; then
                python3 "$SCRIPT" "$CURRENT_INPUT" "$CURRENT_OUTPUT" "$CONFIG_FILE"
            else
                python3 "$SCRIPT" "$CURRENT_INPUT" "$CURRENT_OUTPUT"
            fi
            ;;
        "add_and_fix_reasoning.py")
            python3 "$SCRIPT" "$CURRENT_INPUT" "$CURRENT_OUTPUT"
            ;;
        "replace_system_promptv1.py")
            python3 "$SCRIPT" "$CURRENT_INPUT" "$CURRENT_OUTPUT"
            ;;
        *)
            log_error "Unknown script: $SCRIPT_NAME"
            exit 1
            ;;
    esac
    
    if [ $? -eq 0 ]; then
        log_success "Step $STEP executed successfully"
        
        if [ ! -f "$CURRENT_OUTPUT" ]; then
            log_error "Step $STEP output file not generated: $CURRENT_OUTPUT"
            exit 1
        fi
        
        if ! python3 -m json.tool "$CURRENT_OUTPUT" > /dev/null 2>&1; then
            log_error "Step $STEP output file has invalid JSON format: $CURRENT_OUTPUT"
            exit 1
        fi
        
        log_success "Step $STEP output validation passed"
    else
        log_error "Step $STEP execution failed"
        exit 1
    fi
    
    CURRENT_INPUT="$CURRENT_OUTPUT"
    
    echo
done

log_success "========================================="
log_success "Data processing pipeline completed!"
log_success "Final output file: $OUTPUT_FILE"
log_success "========================================="

if command -v stat > /dev/null 2>&1; then
    ORIGINAL_SIZE=$(stat -c%s "$INPUT_FILE" 2>/dev/null || echo "unknown")
    FINAL_SIZE=$(stat -c%s "$OUTPUT_FILE" 2>/dev/null || echo "unknown")
    log_info "Original file size: $ORIGINAL_SIZE bytes"
    log_info "Final file size: $FINAL_SIZE bytes"
fi
