import Alert from '@mui/material/Alert'

export default function ErrorAlert({ error, onClose }) {
  if (!error) return null

  const message = error instanceof Error ? error.message : String(error)

  return (
    <Alert severity="error" onClose={onClose} sx={{ mb: 2 }}>
      {message}
    </Alert>
  )
}
