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

### Step 2: Generate Structured Specification
Produce a visual-friendly specification with:
- **Directive summary**: 2-3 sentence overview of the SOP approach
- **Steps**: 3-6 labeled steps, each assigned to a DOE layer (directive/orchestration/execution)
- **Execution capabilities**: 2-4 real APIs/tools needed for implementation
- **Edge cases**: 2-3 problematic situations and how the agent handles them
- **Implementation estimate**: Realistic timeline for a PYME
- **Implementation notes**: Additional context or recommendations

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
  "directive_summary": "2-3 sentence summary of the agent's SOP approach",
  "steps": [
    {
      "name": "Step name",
      "description": "1-2 sentence description",
      "layer": "directive|orchestration|execution"
    }
  ],
  "execution_capabilities": [
    {
      "description": "What this capability does",
      "tool": "API or tool name"
    }
  ],
  "edge_cases": ["Edge case 1 and handling", "Edge case 2 and handling"],
  "implementation_estimate": "Realistic time estimate",
  "implementation_notes": "Additional context"
}
```

## Key Messaging
This demo communicates:
1. **We understand your process**: The analysis breaks down what you described into clear steps
2. **DOE Architecture**: Each step is labeled with its layer (Directive/Orchestration/Execution)
3. **Real tools**: We show actual APIs and tools that would be used
4. **We think about edge cases**: Shows the agent anticipates problems
5. **Realistic estimates**: Sets expectations for implementation
6. **No black boxes**: Every step is visible and understandable

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
