import CloudUploadOutlinedIcon from '@mui/icons-material/CloudUploadOutlined'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import { alpha, useTheme } from '@mui/material/styles'
import { useCallback, useRef, useState } from 'react'
import { ACCEPTED_UPLOAD_EXTENSIONS } from '../../constants/transformTypes'

export default function FileUploadPanel({ onFileSelect, disabled, uploadState }) {
  const theme = useTheme()
  const inputRef = useRef(null)
  const [dragOver, setDragOver] = useState(false)

  const handleFiles = useCallback(
    (files) => {
      const file = files?.[0]
      if (file) onFileSelect(file)
    },
    [onFileSelect],
  )

  const statusMessage = {
    idle: 'Drag & drop or click to browse',
    uploading: 'Uploading file…',
    processing: 'Ingesting file on the server…',
    ready: 'File ready — configure a transformation below',
    error: 'Upload failed',
  }[uploadState?.phase ?? 'idle']

  return (
    <Paper sx={{ p: 3 }}>
      <Stack spacing={2}>
        <Box>
          <Typography variant="overline" color="primary">
            Step 1
          </Typography>
          <Typography variant="h6">Upload data</Typography>
          <Typography variant="body2" color="text.secondary">
            CSV and Excel (.xlsx) files are processed asynchronously
          </Typography>
        </Box>

        <Paper
          variant="outlined"
          onDragOver={(event) => {
            event.preventDefault()
            if (!disabled) setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(event) => {
            event.preventDefault()
            setDragOver(false)
            if (!disabled) handleFiles(event.dataTransfer.files)
          }}
          onClick={() => !disabled && inputRef.current?.click()}
          sx={{
            p: 4,
            textAlign: 'center',
            cursor: disabled ? 'not-allowed' : 'pointer',
            opacity: disabled ? 0.7 : 1,
            borderStyle: 'dashed',
            borderWidth: 2,
            bgcolor: dragOver
              ? alpha(theme.palette.primary.main, 0.08)
              : 'background.default',
            borderColor: dragOver ? 'primary.main' : 'divider',
            transition: 'border-color 0.2s, background-color 0.2s',
          }}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED_UPLOAD_EXTENSIONS}
            hidden
            disabled={disabled}
            onChange={(event) => handleFiles(event.target.files)}
          />
          <CloudUploadOutlinedIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
          <Typography variant="subtitle1" fontWeight={600}>
            {uploadState?.filename || 'Choose a file'}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {statusMessage}
          </Typography>
        </Paper>

        {uploadState?.phase === 'ready' && uploadState.columns?.length > 0 && (
          <Box>
            <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ mb: 1, display: 'block' }}>
              DETECTED COLUMNS
            </Typography>
            <Stack direction="row" flexWrap="wrap" gap={1}>
              {uploadState.columns.map((column) => (
                <Chip key={column} label={column} size="small" variant="outlined" />
              ))}
            </Stack>
          </Box>
        )}

        {uploadState?.error && (
          <Alert severity="error">{uploadState.error}</Alert>
        )}
      </Stack>
    </Paper>
  )
}
