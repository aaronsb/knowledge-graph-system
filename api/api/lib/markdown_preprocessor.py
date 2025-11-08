"""
Markdown Structured Content Preprocessing

Implements ADR-023: Translates code blocks and structured content to prose
to prevent parser errors during AGE Cypher ingestion.

Architecture:
1. SERIAL: Parse markdown → AST
2. BOUNDED PARALLEL: Translate code blocks (2-3 workers)
3. SYNC: Wait for all translations
4. SERIAL: Serialize AST → markdown
5. Feed to existing ingestion pipeline
"""

import mistune
import os
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum
import re


class BlockType(Enum):
    """Types of structured content blocks"""
    CODE = "code"
    MERMAID = "mermaid"
    JSON = "json"
    YAML = "yaml"
    TEXT = "text"
    HEADING = "heading"
    LIST = "list"
    OTHER = "other"


@dataclass
class DocumentNode:
    """AST node representing a document element"""
    node_type: BlockType
    content: str
    position: int
    metadata: Dict[str, Any]
    translated: Optional[str] = None

    def __repr__(self):
        preview = self.content[:50].replace('\n', '\\n') if self.content else ""
        return f"<{self.node_type.value}[{self.position}]: {preview}...>"

    def get_text(self) -> str:
        """Get text content (translated if available, otherwise original)"""
        return self.translated if self.translated else self.content


@dataclass
class SemanticChunk:
    """
    Semantic chunk derived from AST nodes.

    Represents a conceptually coherent section of the document,
    grouped from one or more AST nodes while respecting word count limits.

    CRITICAL: Chunks MUST be processed in serial order because each
    concept upsert queries the graph for vector similarity matches.
    Later chunks can link to concepts created by earlier chunks.

    Interface compatible with legacy Chunk for ingestion pipeline.
    """
    text: str
    """Combined text from all nodes (translated content used if available)"""

    chunk_number: int
    """Sequential chunk number (1-indexed, maintains document order)"""

    word_count: int
    """Total word count"""

    boundary_type: str
    """Boundary type: semantic (natural section), hard_cut (fallback), end_of_document"""

    # Interface compatibility with legacy Chunk (not used by process_chunk)
    start_char: int = 0
    """Character position in original document (placeholder for compatibility)"""

    end_char: int = 0
    """Character position in original document (placeholder for compatibility)"""

    # AST-specific metadata
    nodes: List[DocumentNode] = None
    """AST nodes that comprise this chunk"""

    start_position: int = 0
    """Position of first node in AST"""

    end_position: int = 0
    """Position of last node in AST"""


class MarkdownPreprocessor:
    """
    Object-based markdown preprocessing pipeline.

    Parses markdown to AST, translates code blocks to prose,
    serializes back to clean markdown for ingestion.
    """

    def __init__(self,
                 max_workers: int = 3,
                 code_min_lines: int = 3,
                 inline_code_max_length: int = 50,
                 ai_provider = None):
        """
        Args:
            max_workers: Maximum parallel translation workers (default: 3)
            code_min_lines: Minimum lines to translate (strip shorter blocks)
            inline_code_max_length: Max inline code length before translation
            ai_provider: AIProvider instance for translations (optional for testing)
        """
        self.max_workers = max_workers
        self.code_min_lines = code_min_lines
        self.inline_code_max_length = inline_code_max_length
        self.ai_provider = ai_provider

        # Statistics
        self.stats = {
            'blocks_detected': 0,
            'blocks_translated': 0,
            'blocks_stripped': 0,
            'blocks_kept': 0,
            'translation_tokens': 0,  # Track token usage for cost estimation
        }

    def preprocess(self, markdown_content: str) -> str:
        """
        Main preprocessing pipeline.

        Args:
            markdown_content: Raw markdown string

        Returns:
            Cleaned markdown with code blocks translated to prose
        """
        # Stage 1: Parse to AST
        ast = self._parse_to_ast(markdown_content)

        # Stage 2-3: Translate code blocks (bounded parallel + sync)
        ast = self._translate_blocks_parallel(ast)

        # Stage 4: Serialize back to markdown
        cleaned_markdown = self._serialize_ast(ast)

        return cleaned_markdown

    def _parse_to_ast(self, content: str) -> List[DocumentNode]:
        """
        Stage 1: Parse markdown into ordered AST.

        Uses mistune to identify structured blocks and create
        DocumentNode objects with position preserved.
        """
        ast = []
        position = 0

        # Parse markdown using mistune
        markdown = mistune.create_markdown(renderer='ast')
        tokens = markdown(content)

        # Convert mistune tokens to our DocumentNode format
        ast = self._tokens_to_nodes(tokens, position)

        return ast

    def _tokens_to_nodes(self, tokens: List[Dict], start_position: int = 0) -> List[DocumentNode]:
        """
        Convert mistune AST tokens to DocumentNode objects AS SECTIONS.

        CRITICAL FIX: Group content by heading sections, not individual lines.
        - A ## heading + all content until next ## = ONE section node
        - A ``` code fence stays WITHIN the section (translated in place later)

        This prevents code blocks from being split across chunks.
        """
        nodes = []
        position = start_position

        # Group tokens into sections by headings
        current_section_heading = None
        current_section_content = []
        current_section_position = position
        section_has_code = False

        def finalize_section():
            """Create a section node from accumulated heading + content"""
            nonlocal current_section_heading, current_section_content, current_section_position, position, section_has_code

            if current_section_heading is None and not current_section_content:
                return  # Nothing to finalize

            # Build section text: heading + content (with code blocks as markdown)
            section_parts = []
            section_metadata = {'has_code': section_has_code}

            if current_section_heading:
                # Add heading line
                heading_level = current_section_heading.get('level', 1)
                heading_text = current_section_heading.get('text', '')
                section_parts.append(f"{'#' * heading_level} {heading_text}")
                section_metadata['level'] = heading_level
                section_metadata['heading'] = heading_text

            # Add all content tokens in this section (INCLUDING code blocks as markdown)
            for content_token in current_section_content:
                token_text = self._token_to_markdown(content_token)
                if token_text.strip():
                    section_parts.append(token_text)

            # Create ONE section node
            section_text = '\n\n'.join(section_parts)

            nodes.append(DocumentNode(
                node_type=BlockType.HEADING if current_section_heading else BlockType.TEXT,
                content=section_text,
                position=current_section_position,
                metadata=section_metadata
            ))

            position += 1

            # Reset section accumulator
            current_section_heading = None
            current_section_content = []
            current_section_position = position
            section_has_code = False

        for token in tokens:
            token_type = token.get('type', 'unknown')

            if token_type == 'heading':
                # BOUNDARY: Start new section - finalize previous
                finalize_section()

                # Extract heading info
                attrs = token.get('attrs', {})
                level = attrs.get('level', 1) if attrs else 1
                text = self._extract_text_from_children(token.get('children', []))

                current_section_heading = {'level': level, 'text': text}
                current_section_content = []
                current_section_position = position
                section_has_code = False

            elif token_type == 'block_code':
                # BOUNDARY: Code block acts as section boundary
                # Finalize section BEFORE code block
                finalize_section()

                # Create separate code node for translation
                attrs = token.get('attrs', {})
                lang = attrs.get('info', '').strip() if attrs else 'text'
                code = token.get('raw', '')

                node_type = self._classify_code_block(lang)
                nodes.append(DocumentNode(
                    node_type=node_type,
                    content=code,
                    position=position,
                    metadata={'language': lang}
                ))
                self.stats['blocks_detected'] += 1
                position += 1

                # Code block finalized, next content starts fresh section
                current_section_heading = None
                current_section_content = []
                current_section_position = position

            else:
                # All other content belongs to current section
                current_section_content.append(token)

        # Finalize last section
        finalize_section()

        return nodes

    def _token_to_markdown(self, token: Dict) -> str:
        """Convert a single token to markdown text"""
        token_type = token.get('type', 'unknown')

        if token_type == 'paragraph':
            return self._extract_text_from_children(token.get('children', []))

        elif token_type == 'list':
            return self._serialize_list(token)

        elif token_type == 'block_code':
            # Preserve code block as markdown (with fences)
            attrs = token.get('attrs', {})
            lang = attrs.get('info', '').strip() if attrs else ''
            code = token.get('raw', '')
            return f"```{lang}\n{code}\n```"

        elif token_type in ['block_quote', 'thematic_break']:
            return token.get('raw', '')

        elif token_type == 'blank_line':
            return ''  # Skip blank lines in section accumulation

        else:
            # Fallback
            return token.get('raw', str(token))

    def _extract_text_from_children(self, children: List[Dict]) -> str:
        """Extract plain text from token children (inline elements)"""
        text_parts = []

        for child in children:
            child_type = child.get('type', '')

            if child_type == 'text':
                text_parts.append(child.get('raw', ''))
            elif child_type == 'codespan':
                # Inline code - keep as-is for now
                text_parts.append(f"`{child.get('raw', '')}`")
            elif child_type == 'strong':
                inner = self._extract_text_from_children(child.get('children', []))
                text_parts.append(f"**{inner}**")
            elif child_type == 'emphasis':
                inner = self._extract_text_from_children(child.get('children', []))
                text_parts.append(f"*{inner}*")
            elif child_type == 'link':
                inner = self._extract_text_from_children(child.get('children', []))
                url = child.get('link', '')
                text_parts.append(f"[{inner}]({url})")
            else:
                # Other inline elements
                text_parts.append(child.get('raw', ''))

        return ''.join(text_parts)

    def _serialize_list(self, list_token: Dict) -> str:
        """Serialize a list token back to markdown"""
        lines = []
        attrs = list_token.get('attrs', {})
        ordered = attrs.get('ordered', False) if attrs else False
        children = list_token.get('children', [])

        for i, item in enumerate(children):
            if item.get('type') == 'list_item':
                # List items have nested blocks (block_text, paragraph, etc.)
                item_children = item.get('children', [])

                # Extract text from all child blocks
                item_parts = []
                for child in item_children:
                    child_type = child.get('type', '')

                    if child_type == 'paragraph':
                        text = self._extract_text_from_children(child.get('children', []))
                        item_parts.append(text)
                    elif child_type == 'block_text':
                        # Mistune 3.x uses block_text for simple list items
                        text = self._extract_text_from_children(child.get('children', []))
                        item_parts.append(text)
                    else:
                        # Other content in list item
                        text = child.get('raw', str(child))
                        item_parts.append(text)

                item_text = ' '.join(item_parts)

                if ordered:
                    lines.append(f"{i+1}. {item_text}")
                else:
                    lines.append(f"- {item_text}")

        return '\n'.join(lines)

    def _classify_code_block(self, language: str) -> BlockType:
        """Classify code block by language"""
        lang_lower = language.lower()

        if lang_lower in ['mermaid', 'mmd']:
            return BlockType.MERMAID
        elif lang_lower in ['json']:
            return BlockType.JSON
        elif lang_lower in ['yaml', 'yml']:
            return BlockType.YAML
        else:
            return BlockType.CODE

    def _translate_blocks_parallel(self, ast: List[DocumentNode]) -> List[DocumentNode]:
        """
        Stage 2-3: Translate code blocks with bounded parallelism.

        Processes code blocks in parallel (up to max_workers),
        waits for all to complete (synchronization point).
        """
        # Identify blocks that need translation
        code_blocks = [
            node for node in ast
            if node.node_type in [BlockType.CODE, BlockType.MERMAID, BlockType.JSON, BlockType.YAML]
        ]

        if not code_blocks:
            return ast

        # If no AI provider, skip translation (for testing AST parsing)
        if self.ai_provider is None:
            for node in code_blocks:
                # Mark as stripped for testing
                node.translated = f"[CODE BLOCK: {node.metadata.get('language', 'unknown')} - {len(node.content.split(chr(10)))} lines]"
                self.stats['blocks_stripped'] += 1
            return ast

        # Bounded parallel translation
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all code blocks for translation
            future_to_node = {
                executor.submit(self._translate_single_block, node): node
                for node in code_blocks
                if self._should_translate(node)
            }

            # Wait for all to complete (synchronization point)
            for future in as_completed(future_to_node):
                node = future_to_node[future]
                try:
                    result = future.result()  # Returns {"text": ..., "tokens": ...}
                    node.translated = result["text"]
                    self.stats['blocks_translated'] += 1
                    self.stats['translation_tokens'] += result.get("tokens", 0)
                except Exception as e:
                    # Fallback: strip on error
                    node.translated = f"[Translation failed: {str(e)}]"
                    self.stats['blocks_stripped'] += 1

        # Mark blocks that weren't translated as stripped
        for node in code_blocks:
            if node.translated is None:
                node.translated = ""
                self.stats['blocks_stripped'] += 1

        return ast

    def _should_translate(self, node: DocumentNode) -> bool:
        """
        Determine if a code block should be translated.

        Heuristics:
        - Too short: Strip (< code_min_lines)
        - Code/Mermaid: Translate
        - JSON/YAML: Describe structure
        """
        line_count = len(node.content.split('\n'))

        if line_count < self.code_min_lines:
            return False

        return True

    def _translate_single_block(self, node: DocumentNode) -> Dict[str, Any]:
        """
        Translate a single code block to prose (isolation).

        Worker receives only the code and language, no context
        from other blocks.

        Returns dict with 'text' and 'tokens' for tracking
        """
        language = node.metadata.get('language', 'unknown')
        code = node.content

        # Build prompt based on block type - focus on CONCEPTS and LABELS, not explanation
        if node.node_type == BlockType.MERMAID:
            prompt = f"""What concepts and ideas does this Mermaid diagram represent?

Diagram:
{code}

Provide:
1. A 1-2 sentence description of what this diagram represents (NOT how it works)
2. 3-5 conceptual labels or keywords that capture the main ideas

Example output format:
"This diagram represents a data processing pipeline with multiple transformation stages. Key concepts include: data ingestion, validation, transformation, storage, error handling."

CRITICAL: Output ONLY plain text sentences and comma-separated labels. NO code, NO syntax, NO special characters.
"""

        elif node.node_type in [BlockType.JSON, BlockType.YAML]:
            prompt = f"""What concepts does this {language} configuration represent?

Configuration:
{code}

Provide:
1. A 1-2 sentence description of what this configuration defines (NOT the specific values)
2. 3-5 conceptual labels or keywords

Example output format:
"This configuration defines database connection settings and resource limits. Key concepts include: connection pooling, authentication, timeout management, performance tuning."

CRITICAL: Output ONLY plain text sentences and comma-separated labels. NO code, NO syntax, NO special characters.
"""

        else:
            prompt = f"""What concepts and ideas does this {language} code represent?

Code:
{code}

Provide:
1. A 1-2 sentence description of what this code represents (NOT a line-by-line explanation)
2. 3-5 conceptual labels or keywords that capture the main ideas

Example output format:
"This code represents graph database schema initialization and extension setup. Key concepts include: schema definition, database extensions, vector similarity, temporal data management, graph structure."

CRITICAL: Output ONLY plain text sentences and comma-separated labels. NO code, NO syntax, NO examples, NO special characters.
"""

        # Call AI provider (using cheap, fast model: gpt-4o-mini or claude-haiku)
        try:
            response = self.ai_provider.translate_to_prose(prompt, code)

            # Post-process: Strip any remaining code syntax that AI might have included
            translated_text = response["text"]
            translated_text = self._strip_code_from_prose(translated_text)

            return {
                "text": translated_text,
                "tokens": response.get("tokens", 0)
            }
        except Exception as e:
            raise Exception(f"AI translation failed: {str(e)}")

    def _strip_code_from_prose(self, text: str) -> str:
        """
        AGGRESSIVE post-processing: Strip ANY code syntax from AI output.

        AI models consistently include code examples despite warnings.
        This uses a whitelist approach: ONLY keep lines that are clearly prose.
        """
        import re

        # Remove fenced code blocks (```...```)
        text = re.sub(r'```[\s\S]*?```', '', text)

        # Remove inline code (`...`)
        text = re.sub(r'`[^`]+`', '', text)

        # AGGRESSIVE line-by-line filtering (whitelist approach)
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()

            # Keep empty lines
            if not stripped:
                cleaned_lines.append(line)
                continue

            # BLACKLIST: Skip lines with code characteristics
            skip_line = False

            # 1. Contains SQL/Cypher/code keywords followed by parenthesis
            if re.search(r'\b(SELECT|CREATE|MATCH|WHERE|RETURN|INSERT|UPDATE|DELETE|MERGE|WITH|BEGIN|COMMIT|MATCH|SET|REMOVE)\s*\(', stripped, re.IGNORECASE):
                skip_line = True

            # 2. Contains SQL/Cypher keywords followed by other keywords (CREATE TABLE, MATCH (...)
            if re.search(r'\b(CREATE|ALTER|DROP|MATCH|MERGE|SET|REMOVE)\s+(TABLE|INDEX|NODE|EDGE|EXTENSION|GRAPH|SCHEMA|\()', stripped, re.IGNORECASE):
                skip_line = True

            # 3. Has parentheses with colons (property syntax: {label: 'value'})
            if re.search(r'\([^)]*:\s*[\'"]', stripped):
                skip_line = True
            if re.search(r'\{[^}]*:\s*[\'"]', stripped):
                skip_line = True

            # 4. Contains escaped quotes (AI quoting code: \'value\')
            if "\\" in stripped and ("\\'" in stripped or '\\"' in stripped):
                skip_line = True

            # 5. Line has many special chars vs words (code-like density)
            word_count = len(re.findall(r'\b[a-zA-Z]{3,}\b', stripped))  # Words with 3+ letters
            special_chars = len(re.findall(r'[(){}\[\];:$=]', stripped))
            if word_count < 4 and special_chars > 2:
                skip_line = True

            # 6. Contains dollar-quoted strings (PostgreSQL specific)
            if '$$' in stripped:
                skip_line = True

            # 7. Ends with semicolon (code statement)
            if stripped.endswith(';'):
                skip_line = True

            # 8. Starts with special chars (indented code)
            if re.match(r'^\s*[(){}\[\];]', line):
                skip_line = True

            # 9. Contains -> or => (function/relationship syntax)
            if '->' in stripped or '=>' in stripped:
                skip_line = True

            # KEEP line if it passed all blacklist checks
            if not skip_line:
                cleaned_lines.append(line)

        text = '\n'.join(cleaned_lines)

        # Clean up excessive whitespace
        text = re.sub(r'\n\n\n+', '\n\n', text)

        return text.strip()

    def _serialize_ast(self, ast: List[DocumentNode]) -> str:
        """
        Stage 4: Serialize AST back to markdown.

        Reconstructs document in original order, with code blocks
        replaced by their translations.
        """
        # Sort by position to maintain order
        ordered_nodes = sorted(ast, key=lambda n: n.position)

        lines = []

        for node in ordered_nodes:
            if node.node_type == BlockType.HEADING:
                # Reconstruct heading with correct level
                level = node.metadata.get('level', 1)
                prefix = '#' * level
                lines.append(f"{prefix} {node.content}")
                lines.append("")  # Blank line after heading

            elif node.node_type == BlockType.TEXT:
                # Plain paragraph
                lines.append(node.content)
                lines.append("")  # Blank line after paragraph

            elif node.node_type == BlockType.LIST:
                # List content (already formatted)
                lines.append(node.content)
                lines.append("")

            elif node.node_type in [BlockType.CODE, BlockType.MERMAID, BlockType.JSON, BlockType.YAML]:
                # Code block - use translation if available
                if node.translated:
                    lines.append(node.translated)
                    lines.append("")
                else:
                    # Fallback: keep original (shouldn't happen)
                    lines.append(f"```{node.metadata.get('language', '')}")
                    lines.append(node.content)
                    lines.append("```")
                    lines.append("")

            elif node.node_type == BlockType.OTHER:
                # Other elements - preserve as-is
                lines.append(node.content)
                lines.append("")

        # Join and clean up excessive blank lines
        markdown = '\n'.join(lines)

        # Remove excessive blank lines (3+ in a row)
        while '\n\n\n' in markdown:
            markdown = markdown.replace('\n\n\n', '\n\n')

        return markdown.strip()

    def get_stats(self) -> Dict[str, int]:
        """Return preprocessing statistics"""
        return self.stats.copy()

    def group_ast_to_semantic_chunks(
        self,
        ast: List[DocumentNode],
        target_words: int = 1000,
        min_words: int = 800,
        max_words: int = 1500
    ) -> List[SemanticChunk]:
        """
        Group AST nodes into semantic chunks for concept extraction.

        Respects natural document boundaries (headings, sections) while
        maintaining target word counts. Critical for serial processing:
        chunks MUST be processed in order for recursive concept upsert.

        Args:
            ast: List of DocumentNode objects (position-ordered)
            target_words: Target words per chunk (default: 1000)
            min_words: Minimum words per chunk (default: 800)
            max_words: Maximum words per chunk (default: 1500)

        Returns:
            List of SemanticChunk objects in document order
        """
        chunks = []
        current_nodes = []
        current_words = 0
        chunk_num = 1

        def finalize_chunk(boundary_type: str):
            """Finalize current chunk and add to list"""
            nonlocal current_nodes, current_words, chunk_num

            if not current_nodes:
                return

            # Combine text from all nodes (using translated if available)
            text_parts = []
            for node in current_nodes:
                node_text = node.get_text()
                if node_text.strip():
                    text_parts.append(node_text)

            combined_text = '\n\n'.join(text_parts)

            # CRITICAL: Apply aggressive code stripping to ENTIRE chunk text
            # This catches code blocks nested in lists, inline examples, etc.
            combined_text = self._strip_code_from_prose(combined_text)

            chunks.append(SemanticChunk(
                nodes=current_nodes.copy(),
                text=combined_text,
                word_count=len(combined_text.split()),  # Recalculate after stripping
                chunk_number=chunk_num,
                boundary_type=boundary_type,
                start_position=current_nodes[0].position,
                end_position=current_nodes[-1].position
            ))

            current_nodes = []
            current_words = 0
            chunk_num += 1

        for node in ast:
            # Skip empty or very small nodes (blank lines, etc.)
            node_text = node.get_text()
            node_words = len(node_text.split())

            if node_words < 5:
                continue

            # FALLBACK: Giant single node (unstructured text like transcripts)
            # This is the LEGITIMATE fallback case - thousands of words without breaks
            if node_words > max_words:
                # Finalize any pending chunk first
                if current_nodes:
                    finalize_chunk("semantic")

                # Hard cut the giant node into chunks
                hard_cut_chunks = self._hard_cut_large_node(
                    node,
                    target_words,
                    max_words,
                    chunk_num
                )
                chunks.extend(hard_cut_chunks)
                chunk_num += len(hard_cut_chunks)
                continue

            # Natural boundary: heading at or past target
            is_heading = node.node_type == BlockType.HEADING
            at_target = current_words >= target_words

            if is_heading and at_target and current_nodes:
                # Finalize chunk at natural section boundary
                finalize_chunk("semantic")

            # Would adding this node exceed max?
            would_exceed = (current_words + node_words) > max_words

            if would_exceed and current_nodes:
                # Must finalize chunk even mid-section
                finalize_chunk("semantic")

            # Add node to current chunk
            current_nodes.append(node)
            current_words += node_words

        # Finalize last chunk
        if current_nodes:
            finalize_chunk("end_of_document")

        return chunks

    def _hard_cut_large_node(
        self,
        node: DocumentNode,
        target_words: int,
        max_words: int,
        start_chunk_num: int
    ) -> List[SemanticChunk]:
        """
        FALLBACK: Hard cut a giant node into chunks.

        This handles the edge case of unstructured text (audio transcripts,
        single giant paragraphs) that exceed max_words without natural breaks.

        Uses same strategy as current chunker: try to break on sentences,
        fallback to word count if no sentence boundaries found.
        """
        chunks = []
        text = node.get_text()
        words = text.split()
        chunk_num = start_chunk_num

        # Sentence boundary pattern
        sentence_pattern = re.compile(r'[.!?]\s+')

        position = 0
        while position < len(words):
            # Extract target chunk of words
            chunk_words = words[position:position + max_words]
            chunk_text = ' '.join(chunk_words)

            # Try to find sentence boundary near target
            if len(chunk_words) >= target_words:
                # Search in the last 20% of chunk for sentence break
                search_start = int(len(chunk_text) * 0.8)
                search_text = chunk_text[search_start:]

                sentence_matches = list(sentence_pattern.finditer(search_text))
                if sentence_matches:
                    # Cut at last sentence in chunk
                    last_match = sentence_matches[-1]
                    cut_pos = search_start + last_match.end()
                    chunk_text = chunk_text[:cut_pos].strip()

                    # Recalculate word count after cut
                    actual_words = len(chunk_text.split())
                    position += actual_words
                else:
                    # No sentence boundary - hard cut at max_words
                    position += len(chunk_words)
            else:
                # Last chunk - take everything remaining
                position += len(chunk_words)

            # Create chunk (note: single node)
            chunks.append(SemanticChunk(
                nodes=[node],
                text=chunk_text,
                word_count=len(chunk_text.split()),
                chunk_number=chunk_num,
                boundary_type="hard_cut",
                start_position=node.position,
                end_position=node.position
            ))

            chunk_num += 1

        return chunks

    def preprocess_to_chunks(
        self,
        markdown_content: str,
        target_words: int = 1000,
        min_words: int = 800,
        max_words: int = 1500
    ) -> List[SemanticChunk]:
        """
        Complete preprocessing pipeline: markdown → AST → semantic chunks.

        This is the primary interface for ingestion. Returns chunks ready
        for serial concept extraction.

        Pipeline stages:
        1. SERIAL: Parse markdown → AST
        2. BOUNDED PARALLEL: Translate code blocks (2-3 workers)
        3. SYNC: Wait for all translations
        4. SERIAL: Group AST → semantic chunks
        5. Return chunks for serial ingestion (CRITICAL: maintains order)

        Args:
            markdown_content: Raw markdown string
            target_words: Target words per chunk
            min_words: Minimum words per chunk
            max_words: Maximum words per chunk

        Returns:
            List of SemanticChunk objects in document order
        """
        # Stage 1: Parse to AST
        ast = self._parse_to_ast(markdown_content)

        # Stage 2-3: Translate code blocks (bounded parallel + sync)
        ast = self._translate_blocks_parallel(ast)

        # Stage 4: Group into semantic chunks
        chunks = self.group_ast_to_semantic_chunks(
            ast,
            target_words=target_words,
            min_words=min_words,
            max_words=max_words
        )

        return chunks


# Standalone test function
def test_preprocessing_without_ai():
    """
    Test AST parsing and serialization without AI translation.
    Verifies document structure is preserved.
    """
    sample_markdown = """# Test Document

This is a test paragraph with some **bold** and *italic* text.

## Code Example

Here's a Cypher query:

```cypher
MATCH (c:Concept {concept_id: $id})
RETURN c.label, c.search_terms
```

And some Python:

```python
def hello():
    print("world")
```

## Lists

1. First item
2. Second item
3. Third item

- Bullet one
- Bullet two

## Conclusion

This tests the AST processing.
"""

    preprocessor = MarkdownPreprocessor(max_workers=3)
    result = preprocessor.preprocess(sample_markdown)

    print("=== ORIGINAL ===")
    print(sample_markdown)
    print("\n=== PROCESSED (No AI) ===")
    print(result)
    print("\n=== STATISTICS ===")
    print(preprocessor.get_stats())

    return result


if __name__ == '__main__':
    test_preprocessing_without_ai()
