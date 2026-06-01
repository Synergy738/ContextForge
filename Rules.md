# Gemini API Operational Constraints for ContextForge

## Rate Limits

- **15 requests per minute (RPM)**
- **1,500 requests per day (RPD)**
- Quota is shared across all API keys within the same Google AI Studio project
- Creating additional keys will NOT bypass rate limits (429 errors)

## Error Handling Requirements

- Expect occasional **RESOURCE_EXHAUSTED** errors during peak global demand
- Implement **exponential backoff** for retry logic
- Handle **429 Too Many Requests** errors gracefully

## Data Privacy Warning

- Free tier data may be used by Google for training and product improvement
- Human reviewers may access prompts and responses
- Do NOT use free tier for sensitive personal data, proprietary source code, or commercial information
- Upgrade to paid tier to disable data training usage
