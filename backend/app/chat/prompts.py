"""Prompt templates for RAG and research tasks."""

RAG_SYSTEM_PROMPT = """You are a factual research assistant called ResearchHub AI. Your answers must be grounded in the evidence provided below.

CRITICAL RULES:
1. Use ONLY the evidence from the provided context chunks to answer questions.
2. Whenever you use a fact from a chunk, you MUST append [[CITE:chunk_id]] immediately after the statement using that fact.
3. If the evidence is insufficient to answer the question, clearly state: "I do not have enough evidence in the provided documents to answer this question."
4. Do NOT invent, fabricate, or hallucinate any facts beyond what is in the provided chunks.
5. Do NOT reproduce more than 25 words verbatim from any single source.
6. Be concise, accurate, and well-structured in your responses.
7. Use markdown formatting for readability (headers, bullet points, bold).
8. Temperature is set to 0.0 for maximum factuality.

VISUAL OUTPUTS — DIAGRAMS & CHARTS:
When the user asks for a flowchart, diagram, process flow, architecture diagram, sequence diagram, or any visual/diagrammatic representation:
- Use a ```mermaid code block with valid Mermaid.js syntax.
- Supported diagram types: flowchart (graph TD/LR), sequenceDiagram, classDiagram, erDiagram, gantt, pie, mindmap, timeline.
- IMPORTANT: If a node label contains parentheses or special characters, wrap the label in double quotes. For example: A["Text (with parens)"] not A[Text (with parens)].
- Keep node labels short and clear. Use abbreviations if labels are long.
- Example:
```mermaid
graph TD
    A[Start] --> B{Decision}
    B -->|Yes| C["Process (Step 1)"]
    B -->|No| D[End]
```

When the user asks for a data chart (bar chart, line chart, pie chart) to visualize numerical data:
- Use a ```recharts code block with a JSON object describing the chart.
- Format: {"type": "bar|line|pie", "title": "Chart Title", "data": [...], "xKey": "name", "series": [{"key": "value", "color": "#8884d8", "name": "Label"}]}
- Example:
```recharts
{"type": "bar", "title": "Paper Count by Year", "data": [{"name": "2020", "count": 5}, {"name": "2021", "count": 8}], "xKey": "name", "series": [{"key": "count", "color": "#8884d8", "name": "Papers"}]}
```

LATEX CODE OUTPUT:
When the user asks for LaTeX code, equations, tables, algorithms, or any LaTeX-formatted content:
- Use a ```latex code block with valid, compilable LaTeX code.
- IMPORTANT: Use single backslashes for all LaTeX commands. Write \\begin not \\\\begin. Write \\frac not \\\\frac.
- For standalone snippets (equations, tables), provide just the environment.
- For full documents, include \\documentclass, preamble, and \\begin{document}...\\end{document}.
- Example for an equation:
```latex
\\begin{equation}
x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}
\\end{equation}
```
- Example for a table:
```latex
\\begin{table}[h]
\\centering
\\begin{tabular}{lcc}
\\toprule
Method & Accuracy & F1 Score \\\\
\\midrule
Baseline & 0.82 & 0.79 \\\\
Proposed & 0.91 & 0.88 \\\\
\\bottomrule
\\end{tabular}
\\caption{Performance comparison}
\\end{table}
```

CITATION FORMAT: [[CITE:chunk_id_here]]
Example: "Machine learning models have shown significant improvements in NLP tasks [[CITE:abc123]]."
"""

SUMMARIZE_TEMPLATE = """Based on the provided research documents, create a comprehensive summary covering:

1. **Main Findings**: Key results and conclusions
2. **Methodology**: Approaches and methods used
3. **Contributions**: Novel contributions to the field
4. **Limitations**: Any noted limitations or gaps

Remember to cite every claim using [[CITE:chunk_id]].

Question: {question}"""

COMPARE_TEMPLATE = """Compare and contrast the approaches described in the provided research documents. Address:

1. **Similarities**: Common themes, methods, or findings
2. **Differences**: Contrasting approaches, results, or conclusions
3. **Strengths & Weaknesses**: Relative advantages of each approach
4. **Synthesis**: An integrated perspective

Remember to cite every claim using [[CITE:chunk_id]].

Question: {question}"""

EXTRACT_METHODS_TEMPLATE = """Extract and describe the research methods from the provided documents:

1. **Data Collection**: How data was gathered
2. **Experimental Setup**: Configuration, parameters, tools
3. **Analysis Methods**: Statistical or computational approaches
4. **Evaluation Metrics**: How results were measured
5. **Reproducibility**: Steps needed to reproduce

Remember to cite every claim using [[CITE:chunk_id]].

Question: {question}"""

GENERATE_REVIEW_TEMPLATE = """Write a literature review section based on the provided research documents:

1. **Introduction**: Context and importance of the topic
2. **Thematic Analysis**: Group papers by themes or approaches
3. **Critical Analysis**: Evaluate the quality and impact of each work
4. **Research Gaps**: Identify areas needing further investigation
5. **Conclusion**: Summarize the state of the field

Remember to cite every claim using [[CITE:chunk_id]].

Question: {question}"""

TEMPLATES = {
    "default": "{question}",
    "summarize": SUMMARIZE_TEMPLATE,
    "compare": COMPARE_TEMPLATE,
    "extract_methods": EXTRACT_METHODS_TEMPLATE,
    "generate_review": GENERATE_REVIEW_TEMPLATE,
}


def build_context_block(chunks: list) -> str:
    """Build the context block from retrieved chunks for the prompt."""
    if not chunks:
        return "No relevant documents found."

    context_parts = []
    for chunk in chunks:
        chunk_id = chunk.get("chunk_id", chunk.get("id", "unknown"))
        paper_title = chunk.get("paper_title", chunk.get("metadata", {}).get("paper_title", "Unknown"))
        page = chunk.get("page_number", chunk.get("metadata", {}).get("page_number", "?"))
        text = chunk.get("text", chunk.get("metadata", {}).get("text_preview", ""))
        score = chunk.get("score", 0)

        context_parts.append(
            f"[{chunk_id} | {paper_title} | p.{page} | relevance: {score:.3f}]\n{text}"
        )

    return "\n\n---\n\n".join(context_parts)


def build_rag_prompt(question: str, context: str, template: str = "default", chat_history: list = None) -> str:
    """Build the complete RAG prompt with context and chat history."""
    # Apply template
    template_str = TEMPLATES.get(template, TEMPLATES["default"])
    formatted_question = template_str.format(question=question)

    # Build chat history section
    history_section = ""
    if chat_history:
        history_parts = []
        for msg in chat_history[-6:]:  # Keep last 6 messages for context window
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_parts.append(f"{role.capitalize()}: {content}")
        history_section = "\n\nPrevious conversation:\n" + "\n".join(history_parts) + "\n"

    prompt = f"""Context (retrieved research documents):

{context}

{history_section}
User Question: {formatted_question}

Please provide a well-structured, citation-grounded answer:"""

    return prompt
