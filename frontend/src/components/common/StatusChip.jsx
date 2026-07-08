import Chip from '@mui/material/Chip'

const STATUS_COLOR = {
  QUEUED: 'info',
  RUNNING: 'info',
  SUCCESS: 'success',
  FAILED: 'error',
  CANCELLED: 'default',
  ready: 'success',
  processing: 'warning',
}

export default function StatusChip({ status, label, size = 'small' }) {
  return (
    <Chip
      size={size}
      label={label ?? status}
      color={STATUS_COLOR[status] ?? 'default'}
      variant={status === 'CANCELLED' ? 'outlined' : 'filled'}
    />
  )
}
