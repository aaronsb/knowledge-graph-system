/**
 * Terminal Image Display Utilities (ADR-057)
 *
 * Provides utilities for displaying images in the terminal using chafa,
 * with fallback options and configuration support.
 */

import { execSync, spawnSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import chalk from 'chalk';

/**
 * Check if chafa is available on the system
 * @returns true if chafa command is available
 */
export function isChafaAvailable(): boolean {
  try {
    execSync('which chafa', { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

/**
 * Get chafa version information
 * @returns Version string or null if not available
 */
export function getChafaVersion(): string | null {
  try {
    const output = execSync('chafa --version', { encoding: 'utf-8' });
    const match = output.match(/chafa version (\S+)/i);
    return match ? match[1] : output.trim();
  } catch {
    return null;
  }
}

export interface ChafaOptions {
  /** Width in characters (default: terminal width) */
  width?: number;
  /** Height in characters (default: auto) */
  height?: number;
  /** Color mode: 256 (default), 16, 2, or full (truecolor) */
  colors?: '256' | '16' | '2' | 'full';
  /** Symbol map: block, border, space, vhalf, etc. */
  symbols?: string;
  /** Enable animations for GIFs (default: false) */
  animate?: boolean;
}

/**
 * Display image in terminal using chafa
 * @param imagePath - Path to image file
 * @param options - Chafa display options
 * @returns true if successfully displayed, false otherwise
 */
export function displayImageWithChafa(imagePath: string, options: ChafaOptions = {}): boolean {
  if (!isChafaAvailable()) {
    return false;
  }

  // Build chafa command arguments
  const args: string[] = [];

  // Size options
  if (options.width) {
    args.push('--size', `${options.width}x${options.height || ''}`);
  } else {
    // Auto-size to terminal width (leave some margin)
    const termWidth = process.stdout.columns || 80;
    args.push('--size', `${Math.min(termWidth - 4, 120)}x`);
  }

  // Color mode
  if (options.colors) {
    if (options.colors === 'full') {
      args.push('--colors', 'full');
    } else {
      args.push('--colors', options.colors);
    }
  } else {
    // Default to 256 colors for best compatibility
    args.push('--colors', '256');
  }

  // Symbol map
  if (options.symbols) {
    args.push('--symbols', options.symbols);
  } else {
    // Use block symbols for better image quality
    args.push('--symbols', 'block');
  }

  // Animation (for GIFs)
  if (options.animate === false) {
    args.push('--animate', 'off');
  }

  // Add image path
  args.push(imagePath);

  try {
    // Execute chafa synchronously to display image
    const result = spawnSync('chafa', args, {
      stdio: 'inherit',
      encoding: 'utf-8',
    });

    return result.status === 0;
  } catch (error) {
    console.error(chalk.yellow(`Failed to display image with chafa: ${error}`));
    return false;
  }
}

/**
 * Display image from Buffer using chafa
 * Writes to temp file, displays, then cleans up
 * @param imageBuffer - Image binary data
 * @param extension - File extension (e.g., '.jpg', '.png')
 * @param options - Chafa display options
 * @returns true if successfully displayed
 */
export async function displayImageBufferWithChafa(
  imageBuffer: Buffer,
  extension: string = '.jpg',
  options: ChafaOptions = {}
): Promise<boolean> {
  if (!isChafaAvailable()) {
    return false;
  }

  // Create temp file
  const tmpDir = os.tmpdir();
  const tmpFile = path.join(tmpDir, `kg-image-${Date.now()}${extension}`);

  try {
    // Write buffer to temp file
    fs.writeFileSync(tmpFile, imageBuffer);

    // Display with chafa
    const success = displayImageWithChafa(tmpFile, options);

    return success;
  } catch (error) {
    console.error(chalk.yellow(`Failed to display image: ${error}`));
    return false;
  } finally {
    // Clean up temp file
    try {
      if (fs.existsSync(tmpFile)) {
        fs.unlinkSync(tmpFile);
      }
    } catch {
      // Ignore cleanup errors
    }
  }
}

/**
 * Save image buffer to file
 * @param imageBuffer - Image binary data
 * @param outputPath - Path to save image
 * @returns true if successfully saved
 */
export function saveImageToFile(imageBuffer: Buffer, outputPath: string): boolean {
  try {
    // Ensure directory exists
    const dir = path.dirname(outputPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    // Write file
    fs.writeFileSync(outputPath, imageBuffer);
    return true;
  } catch (error) {
    console.error(chalk.red(`Failed to save image: ${error}`));
    return false;
  }
}

/**
 * Get image format from buffer by checking magic bytes
 * @param buffer - Image binary data
 * @returns File extension (with dot) or '.jpg' as fallback
 */
export function detectImageFormat(buffer: Buffer): string {
  if (buffer.length < 12) {
    return '.jpg'; // Fallback
  }

  // Check magic bytes
  // PNG: 89 50 4E 47 0D 0A 1A 0A
  if (buffer[0] === 0x89 && buffer[1] === 0x50 && buffer[2] === 0x4E && buffer[3] === 0x47) {
    return '.png';
  }

  // JPEG: FF D8 FF
  if (buffer[0] === 0xFF && buffer[1] === 0xD8 && buffer[2] === 0xFF) {
    return '.jpg';
  }

  // GIF: 47 49 46 38
  if (buffer[0] === 0x47 && buffer[1] === 0x49 && buffer[2] === 0x46 && buffer[3] === 0x38) {
    return '.gif';
  }

  // WebP: 52 49 46 46 ... 57 45 42 50
  if (buffer[0] === 0x52 && buffer[1] === 0x49 && buffer[2] === 0x46 && buffer[3] === 0x46 &&
      buffer[8] === 0x57 && buffer[9] === 0x45 && buffer[10] === 0x42 && buffer[11] === 0x50) {
    return '.webp';
  }

  // BMP: 42 4D
  if (buffer[0] === 0x42 && buffer[1] === 0x4D) {
    return '.bmp';
  }

  return '.jpg'; // Fallback to JPEG
}

/**
 * Print chafa installation instructions
 */
export function printChafaInstallInstructions(): void {
  console.log(chalk.yellow('\n⚠️  chafa is not installed\n'));
  console.log('To display images inline in the terminal, install chafa:\n');
  console.log(chalk.cyan('  # macOS'));
  console.log(chalk.gray('  brew install chafa\n'));
  console.log(chalk.cyan('  # Ubuntu/Debian'));
  console.log(chalk.gray('  sudo apt install chafa\n'));
  console.log(chalk.cyan('  # Fedora'));
  console.log(chalk.gray('  sudo dnf install chafa\n'));
  console.log(chalk.cyan('  # Arch Linux'));
  console.log(chalk.gray('  sudo pacman -S chafa\n'));
  console.log('You can still use --download to save images to a file.\n');
}
