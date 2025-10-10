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
                    translated = future.result()
                    node.translated = translated
                    self.stats['blocks_translated'] += 1
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

    def _translate_single_block(self, node: DocumentNode) -> str:
        """
        Translate a single code block to prose (isolation).

        Worker receives only the code and language, no context
        from other blocks.
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

Provide only the prose explanation, no code or diagram syntax."""

        elif node.node_type in [BlockType.JSON, BlockType.YAML]:
            prompt = f"""Describe this {language} configuration in plain English prose.
Explain what this configuration defines, key settings, and their purpose.
Use simple paragraphs. Focus on WHAT it configures and WHY.

Configuration:
{code}

Provide only the prose description, no code syntax."""

        else:
            prompt = f"""Explain this {language} code in plain English prose.
Describe what the code does, how it works, and its purpose.
Use simple paragraphs and lists. Focus on WHAT it does and WHY.

Code:
{code}

Provide only the prose explanation, no code syntax."""

        # Call AI provider (using cheap, fast model)
        try:
            # Use the AI provider's generate method
            # For testing, we can mock this
            response = self.ai_provider.translate_code_to_prose(prompt)
            return response
        except Exception as e:
            raise Exception(f"AI translation failed: {str(e)}")

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
