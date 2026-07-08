export const TRANSFORM_TYPES = {
  REGEX_REPLACE: 'REGEX_REPLACE',
  LITERAL_REPLACE: 'LITERAL_REPLACE',
}

export const TRANSFORM_TYPE_OPTIONS = [
  {
    value: TRANSFORM_TYPES.REGEX_REPLACE,
    label: 'Pattern match (regex)',
    description: 'Describe a pattern in natural language. An LLM converts it to regex and replaces matches.',
  },
  {
    value: TRANSFORM_TYPES.LITERAL_REPLACE,
    label: 'Literal find & replace',
    description: 'Describe what to find and what to replace it with. The LLM extracts exact values.',
  },
]

export const JOB_STATUS_LABELS = {
  QUEUED: 'Queued',
  RUNNING: 'Running',
  SUCCESS: 'Complete',
  FAILED: 'Failed',
  CANCELLED: 'Cancelled',
}

export const TERMINAL_JOB_STATUSES = new Set(['SUCCESS', 'FAILED', 'CANCELLED'])

export const ACCEPTED_UPLOAD_EXTENSIONS = '.csv,.xlsx'
