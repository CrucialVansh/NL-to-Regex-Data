import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import LinearProgress from '@mui/material/LinearProgress'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import {
  JOB_STATUS_LABELS,
  TERMINAL_JOB_STATUSES,
  TRANSFORM_TYPE_OPTIONS,
} from '../../constants/transformTypes'
import { formatRowProgress } from '../../utils/format'
import StatusChip from '../common/StatusChip'

export default function JobProgressPanel({ job, onCancel, cancelling }) {
  if (!job) return null

  const isActive = !TERMINAL_JOB_STATUSES.has(job.status)
  const rowProgress = formatRowProgress(job.rows_processed, job.total_rows)
  const transformLabel = TRANSFORM_TYPE_OPTIONS.find(
    (option) => option.value === job.transform_type,
  )?.label

  return (
    <Paper sx={{ p: 3 }}>
      <Stack spacing={2}>
        <Box>
          <Typography variant="overline" color="primary">
            Step 3
          </Typography>
          <Typography variant="h6">Job status</Typography>
          <Typography variant="body2" color="text.secondary">
            Processing runs in the background — this page stays responsive
          </Typography>
        </Box>

        <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" spacing={2}>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="caption" color="text.secondary" fontWeight={600}>
              JOB ID
            </Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>
              {job.job_id}
            </Typography>
            {transformLabel && (
              <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                {transformLabel}
              </Typography>
            )}
          </Box>
          <StatusChip
            status={job.status}
            label={JOB_STATUS_LABELS[job.status] ?? job.status}
          />
        </Stack>

        {isActive && (
          <Box>
            <Stack direction="row" justifyContent="space-between" sx={{ mb: 1 }}>
              <Typography variant="body2" color="text.secondary">
                {job.progress ?? 0}% complete
              </Typography>
              {rowProgress && (
                <Typography variant="body2" color="text.secondary">
                  {rowProgress}
                </Typography>
              )}
            </Stack>
            <LinearProgress variant="determinate" value={job.progress ?? 0} />
          </Box>
        )}

        {job.retry_message && isActive && (
          <Alert severity="info">{job.retry_message}</Alert>
        )}

        {job.status === 'FAILED' && job.error && (
          <Alert severity="error">{job.error}</Alert>
        )}

        {job.status === 'CANCELLED' && (
          <Alert severity="warning">{job.message || 'Job was cancelled'}</Alert>
        )}

        {job.status === 'SUCCESS' && (
          <Alert severity="success">
            Transformation finished
            {job.generated_regex && (
              <>
                {' '}
                — regex:{' '}
                <Box component="span" sx={{ fontFamily: 'monospace' }}>
                  {job.generated_regex}
                </Box>
              </>
            )}
            {job.find_value && (
              <>
                {' '}
                — find: <strong>{job.find_value}</strong>, replace:{' '}
                <strong>{job.replacement_value}</strong>
              </>
            )}
          </Alert>
        )}

        {isActive && (
          <Button
            variant="outlined"
            color="inherit"
            startIcon={<CancelOutlinedIcon />}
            onClick={onCancel}
            disabled={cancelling}
          >
            {cancelling ? 'Cancelling…' : 'Cancel job'}
          </Button>
        )}
      </Stack>
    </Paper>
  )
}
