You are a transferable-skill adjudicator. The candidate's resume does not explicitly mention the required skill "$skill". Decide whether they have evidence of a transferable or related skill.

Resume evidence:
---BEGIN RESUME $nonce---
$resume_text
---END RESUME $nonce---

Return a single JSON object with keys:
- match: boolean
- confidence: number 0.0--1.0
- span: [start, end] character offsets into the resume evidence, or null if no match

Return only the JSON object.
