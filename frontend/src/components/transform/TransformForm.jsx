import LoadingButton from '@mui/lab/LoadingButton'
import Box from '@mui/material/Box'
import Checkbox from '@mui/material/Checkbox'
import FormControl from '@mui/material/FormControl'
import FormControlLabel from '@mui/material/FormControlLabel'
import FormGroup from '@mui/material/FormGroup'
import FormHelperText from '@mui/material/FormHelperText'
import FormLabel from '@mui/material/FormLabel'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Select from '@mui/material/Select'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import {
  TRANSFORM_TYPE_OPTIONS,
  TRANSFORM_TYPES,
} from '../../constants/transformTypes'

export default function TransformForm({
  columns,
  transformType,
  naturalLanguagePrompt,
  replacementValue,
  selectedColumns,
  onTransformTypeChange,
  onPromptChange,
  onReplacementChange,
  onColumnToggle,
  onSubmit,
  disabled,
  submitting,
}) {
  const isRegex = transformType === TRANSFORM_TYPES.REGEX_REPLACE
  const canSubmit =
    !disabled &&
    !submitting &&
    naturalLanguagePrompt.trim() &&
    selectedColumns.length > 0 &&
    (isRegex ? replacementValue.trim() : true)

  const selectedTransform = TRANSFORM_TYPE_OPTIONS.find((opt) => opt.value === transformType)

  return (
    <Paper sx={{ p: 3 }}>
      <Stack spacing={3}>
        <Box>
          <Typography variant="overline" color="primary">
            Step 2
          </Typography>
          <Typography variant="h6">Configure transformation</Typography>
          <Typography variant="body2" color="text.secondary">
            Choose a transform type and describe what to change in plain English
          </Typography>
        </Box>

        <FormControl fullWidth disabled={disabled}>
          <FormLabel sx={{ mb: 1 }}>Transform type</FormLabel>
          <Select
            value={transformType}
            onChange={(event) => onTransformTypeChange(event.target.value)}
          >
            {TRANSFORM_TYPE_OPTIONS.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
          {selectedTransform && (
            <FormHelperText>{selectedTransform.description}</FormHelperText>
          )}
        </FormControl>

        <TextField
          label="Natural language instruction"
          multiline
          minRows={3}
          fullWidth
          disabled={disabled}
          value={naturalLanguagePrompt}
          onChange={(event) => onPromptChange(event.target.value)}
          placeholder={
            isRegex
              ? 'e.g. Find email addresses in the Email column'
              : 'e.g. Replace john.doe@example.com with REDACTED in the Email column'
          }
          helperText="Up to 2,000 characters"
        />

        {isRegex && (
          <TextField
            label="Replacement value"
            fullWidth
            disabled={disabled}
            value={replacementValue}
            onChange={(event) => onReplacementChange(event.target.value)}
            placeholder="e.g. REDACTED"
          />
        )}

        <FormControl component="fieldset" disabled={disabled || !columns.length} fullWidth>
          <FormLabel component="legend" sx={{ mb: 1 }}>
            Target column(s)
          </FormLabel>
          {!columns.length ? (
            <FormHelperText>Upload a file to see available columns</FormHelperText>
          ) : (
            <FormGroup row sx={{ gap: 1 }}>
              {columns.map((column) => (
                <FormControlLabel
                  key={column}
                  control={
                    <Checkbox
                      checked={selectedColumns.includes(column)}
                      onChange={() => onColumnToggle(column)}
                    />
                  }
                  label={column}
                />
              ))}
            </FormGroup>
          )}
        </FormControl>

        <LoadingButton
          variant="contained"
          size="large"
          loading={submitting}
          disabled={!canSubmit}
          onClick={onSubmit}
        >
          Run transformation
        </LoadingButton>
      </Stack>
    </Paper>
  )
}
