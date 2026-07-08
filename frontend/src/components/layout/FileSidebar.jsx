import { useEffect, useState } from 'react'
import AddIcon from '@mui/icons-material/Add'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import InsertDriveFileOutlinedIcon from '@mui/icons-material/InsertDriveFileOutlined'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Collapse from '@mui/material/Collapse'
import Divider from '@mui/material/Divider'
import IconButton from '@mui/material/IconButton'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemText from '@mui/material/ListItemText'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import { JOB_STATUS_LABELS } from '../../constants/transformTypes'
import { formatDateTime } from '../../utils/format'
import StatusChip from '../common/StatusChip'

function FileJobsList({ jobs, activeJobId, onSelectJob, fileId }) {
  if (!jobs?.length) {
    return (
      <Typography variant="caption" color="text.secondary" sx={{ px: 2, py: 1, display: 'block' }}>
        No jobs yet
      </Typography>
    )
  }

  return (
    <List dense disablePadding>
      {jobs.map((job) => (
        <ListItemButton
          key={job.job_id}
          selected={activeJobId === job.job_id}
          onClick={() => onSelectJob(job.job_id, fileId)}
          sx={{ pl: 4, py: 1 }}
        >
          <ListItemText
            primary={job.natural_language_prompt}
            secondary={
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
                <StatusChip
                  status={job.status}
                  label={JOB_STATUS_LABELS[job.status] ?? job.status}
                />
                {job.status === 'RUNNING' && (
                  <Typography variant="caption" color="primary.main">
                    {job.progress}%
                  </Typography>
                )}
                <Typography variant="caption" color="text.secondary">
                  {formatDateTime(job.created_at)}
                </Typography>
              </Stack>
            }
            primaryTypographyProps={{ variant: 'body2', noWrap: true }}
          />
        </ListItemButton>
      ))}
    </List>
  )
}

function FileListItem({
  file,
  activeFileId,
  activeJobId,
  expanded,
  onToggleExpand,
  onSelectFile,
  onSelectJob,
}) {
  const isActive = activeFileId === file.uploaded_file_id

  return (
    <Box>
      <ListItemButton selected={isActive} onClick={() => onSelectFile(file.uploaded_file_id)} sx={{ py: 1.25 }}>
        <InsertDriveFileOutlinedIcon color="action" sx={{ mr: 1.5, fontSize: 20 }} />
        <ListItemText
          primary={file.filename}
          secondary={
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mt: 0.5 }}>
              <StatusChip status={file.status} label={file.status === 'ready' ? 'Ready' : 'Processing'} />
              <Typography variant="caption" color="text.secondary">
                {formatDateTime(file.uploaded_at)}
              </Typography>
            </Stack>
          }
          primaryTypographyProps={{ variant: 'body2', fontWeight: 600, noWrap: true }}
        />
        <IconButton
          size="small"
          aria-label={expanded ? 'Collapse jobs' : 'Expand jobs'}
          onClick={(event) => {
            event.stopPropagation()
            onToggleExpand(file.uploaded_file_id)
          }}
        >
          {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
        </IconButton>
      </ListItemButton>

      <Collapse in={expanded} timeout="auto" unmountOnExit>
        <FileJobsList
          jobs={file.jobs}
          activeJobId={activeJobId}
          onSelectJob={onSelectJob}
          fileId={file.uploaded_file_id}
        />
      </Collapse>
    </Box>
  )
}

export default function FileSidebar({
  uploads,
  isLoading,
  activeFileId,
  activeJobId,
  onSelectFile,
  onSelectJob,
  onNewUpload,
}) {
  const [expandedFiles, setExpandedFiles] = useState(() => new Set())

  useEffect(() => {
    if (activeFileId) {
      setExpandedFiles((prev) => new Set(prev).add(activeFileId))
    }
  }, [activeFileId])

  const toggleExpanded = (fileId) => {
    setExpandedFiles((prev) => {
      const next = new Set(prev)
      if (next.has(fileId)) next.delete(fileId)
      else next.add(fileId)
      return next
    })
  }

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        sx={{ px: 2, py: 2 }}
      >
        <Typography variant="h6">Files</Typography>
        <Button size="small" startIcon={<AddIcon />} onClick={onNewUpload}>
          New upload
        </Button>
      </Stack>

      <Divider />

      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {isLoading && !uploads.length && (
          <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
            Loading files…
          </Typography>
        )}

        {!isLoading && !uploads.length && (
          <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
            No uploads yet. Start with a new file.
          </Typography>
        )}

        <List disablePadding>
          {uploads.map((file) => (
            <FileListItem
              key={file.uploaded_file_id}
              file={file}
              activeFileId={activeFileId}
              activeJobId={activeJobId}
              expanded={expandedFiles.has(file.uploaded_file_id)}
              onToggleExpand={toggleExpanded}
              onSelectFile={onSelectFile}
              onSelectJob={onSelectJob}
            />
          ))}
        </List>
      </Box>
    </Box>
  )
}
