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
        Convert mistune AST tokens to DocumentNode objects.

        Recursively processes tokens and maintains position order.
        """
        nodes = []
        position = start_position

        for token in tokens:
            token_type = token.get('type', 'unknown')

            if token_type == 'block_code':
                # Fenced code block - get language from attrs.info
                attrs = token.get('attrs', {})
                lang = attrs.get('info', '').strip() if attrs else 'text'
                if not lang:
                    lang = 'text'
                code = token.get('raw', '')

                node_type = self._classify_code_block(lang)
                nodes.append(DocumentNode(
                    node_type=node_type,
                    content=code,
                    position=position,
                    metadata={'language': lang}
                ))
                self.stats['blocks_detected'] += 1

            elif token_type == 'heading':
                # Heading - level is in attrs
                attrs = token.get('attrs', {})
                level = attrs.get('level', 1) if attrs else 1
                # Extract text from children
                text = self._extract_text_from_children(token.get('children', []))
                nodes.append(DocumentNode(
                    node_type=BlockType.HEADING,
                    content=text,
                    position=position,
                    metadata={'level': level}
                ))

            elif token_type == 'paragraph':
                # Paragraph - extract text from children
                text = self._extract_text_from_children(token.get('children', []))
                nodes.append(DocumentNode(
                    node_type=BlockType.TEXT,
                    content=text,
                    position=position,
                    metadata={}
                ))

            elif token_type == 'list':
                # List - serialize children as markdown
                # ordered flag is in attrs in mistune 3.x
                attrs = token.get('attrs', {})
                ordered = attrs.get('ordered', False) if attrs else False
                list_content = self._serialize_list(token)
                nodes.append(DocumentNode(
                    node_type=BlockType.LIST,
                    content=list_content,
                    position=position,
                    metadata={'ordered': ordered}
                ))

            elif token_type in ['block_quote', 'thematic_break', 'blank_line']:
                # Other block-level elements
                raw = token.get('raw', '')
                nodes.append(DocumentNode(
                    node_type=BlockType.OTHER,
                    content=raw,
                    position=position,
                    metadata={'original_type': token_type}
                ))

            else:
                # Unknown token - preserve as-is
                raw = str(token)
                nodes.append(DocumentNode(
                    node_type=BlockType.OTHER,
                    content=raw,
                    position=position,
                    metadata={'original_type': token_type}
                ))

            position += 1

        return nodes

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

        # Build prompt based on block type
        if node.node_type == BlockType.MERMAID:
            prompt = f"""Explain this Mermaid diagram in plain English prose.
Describe what the diagram shows, the flow or relationships, and the key components.
Use simple paragraphs. Focus on WHAT it represents and WHY.

Diagram:
{code}

⚠️  NEVER UNDER ANY CIRCUMSTANCES INCLUDE CODE SYNTAX IN YOUR RESPONSE ⚠️
YOU WILL BREAK THE ENTIRE SYSTEM IF YOU INCLUDE ANY:
- Mermaid syntax (graph TD, -->, etc.)
- Code blocks, backticks, or fenced syntax
- Technical symbols or operators
- ANY non-prose content

ONLY provide natural language prose. Write as if explaining to someone verbally.
Example: "The diagram shows data flowing from the user interface through an API layer to the database."
"""

        elif node.node_type in [BlockType.JSON, BlockType.YAML]:
            prompt = f"""Describe this {language} configuration in plain English prose.
Explain what this configuration defines, key settings, and their purpose.
Use simple paragraphs. Focus on WHAT it configures and WHY.

Configuration:
{code}

⚠️  NEVER UNDER ANY CIRCUMSTANCES INCLUDE CODE SYNTAX IN YOUR RESPONSE ⚠️
YOU WILL BREAK THE ENTIRE SYSTEM IF YOU INCLUDE ANY:
- JSON, YAML, or configuration syntax
- Curly braces, brackets, colons, or quotes
- Code blocks or backticks
- ANY non-prose content

ONLY provide natural language prose. Write as if explaining to someone verbally.
Example: "This configuration sets up a PostgreSQL database container with specific credentials and port mappings."
"""

        else:
            prompt = f"""Explain this {language} code in plain English prose.
Describe what the code does, how it works, and its purpose.
Use simple paragraphs and lists. Focus on WHAT it does and WHY.

Code:
{code}

⚠️  NEVER UNDER ANY CIRCUMSTANCES INCLUDE CODE SYNTAX IN YOUR RESPONSE ⚠️
YOU WILL BREAK THE ENTIRE SYSTEM IF YOU INCLUDE ANY:
- SQL statements (CREATE, SELECT, INSERT, MATCH, WHERE, RETURN)
- Cypher queries (MATCH, CREATE, MERGE, etc.)
- Programming syntax (brackets, semicolons, operators)
- Code blocks, backticks, or fenced syntax
- ANY non-prose content whatsoever

ONLY provide natural language prose. Write as if explaining to someone verbally.
Do NOT show examples of the code. Describe what it does in plain English only.
Example: "This code creates a new concept node in the graph database and logs the action to an audit table within a transaction."
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
        Post-processing: Strip any code syntax that AI might have included despite warnings.

        This is a safety net for when AI doesn't follow instructions perfectly.
        Removes common code patterns while preserving natural language.
        """
        import re

        # Remove fenced code blocks (```...```)
        text = re.sub(r'```[\s\S]*?```', '[code example removed]', text)

        # Remove inline code (`...`)
        text = re.sub(r'`[^`]+`', '', text)

        # Remove lines that LOOK like code (multiple heuristics)
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                cleaned_lines.append(line)
                continue

            # Heuristic 1: Line starts with SQL/Cypher keyword
            if re.match(r'^\s*(SELECT|CREATE|MATCH|WHERE|RETURN|INSERT|UPDATE|DELETE|MERGE|WITH|BEGIN|COMMIT)\b', line, re.IGNORECASE):
                continue  # Skip this line

            # Heuristic 2: Line looks like code (has operators/brackets but few words)
            word_count = len(re.findall(r'\b\w+\b', stripped))
            special_chars = len(re.findall(r'[(){}\[\];:$]', stripped))
            if word_count < 5 and special_chars > 2:
                continue  # Likely code, skip

            # Heuristic 3: Line contains dollar-quoted strings (PostgreSQL/AGE specific)
            if '$$' in stripped:
                continue  # Skip

            # Heuristic 4: Line has assignment operators or ends with semicolon
            if re.search(r'\s*=\s*[^\s]|;\s*$', stripped):
                continue  # Likely code

            # Keep this line (seems like prose)
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

            chunks.append(SemanticChunk(
                nodes=current_nodes.copy(),
                text=combined_text,
                word_count=current_words,
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
