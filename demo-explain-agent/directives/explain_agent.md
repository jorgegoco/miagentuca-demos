# Explain Agent Directive

## Purpose
Demonstrate the 3-layer AI agent architecture by generating a complete agent specification from a business process description. This is the "meta demo" that shows potential clients exactly how we build reliable AI solutions.

## Input
- **process_description**: Natural language description of a business process to automate
- **language**: Output language (default: Spanish)

## Process

### Step 1: Analyze the Business Process
Extract from the description:
- Main goal/objective
- Input data types
- Output/deliverables
- Key decision points
- Edge cases and error scenarios

### Step 2: Generate the Directive (Layer 1)
Create a markdown SOP that includes:
- Purpose statement
- Input specifications
- Step-by-step process
- Output format
- Edge cases

### Step 3: Generate Execution Code (Layer 3)
Create Python code skeleton for:
- Data validation functions
- Core processing logic
- Output formatting
- Error handling

### Step 4: Generate Architecture Diagram
Create a Mermaid flowchart showing:
- The 3 layers and their interactions
- Data flow between components
- Decision points
- External API calls

## Output Format (JSON)
```json
{
  "success": true,
  "process_analysis": {
    "goal": "string",
    "inputs": ["list of inputs"],
    "outputs": ["list of outputs"],
    "complexity": "low|medium|high"
  },
  "directive": "markdown string",
  "execution_code": "python code string",
  "flowchart": "mermaid diagram string",
  "implementation_notes": "string"
}
```

## Key Messaging
This demo should communicate:
1. **Transparency**: "This is exactly how we build your solution"
2. **Reliability**: "Deterministic code + AI decision-making = consistent results"
3. **Maintainability**: "Clear separation of concerns makes updates easy"
4. **No black boxes**: "You can read, understand, and audit everything"

## Edge Cases

### Vague description
Ask for clarification or make reasonable assumptions, noting them.

### Too complex for demo
Simplify to core workflow, note that full implementation would require deeper analysis.

### Non-automatable process
Explain why and suggest which parts could be automated.

## Spanish Context
- Output in Spanish by default
- Use Spanish business terminology
- Examples relevant to Spanish SMEs
