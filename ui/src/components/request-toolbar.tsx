interface RequestToolbarProps {
  selectedCount: number
  totalCount: number
  onSelectAll: () => void
  onInvert: () => void
  onDelete: () => void
}

export function RequestToolbar({
  selectedCount,
  totalCount,
  onSelectAll,
  onInvert,
  onDelete,
}: RequestToolbarProps) {
  return (
    <div class="toolbar">
      <div class="toolbar__title">
        <strong>Requests</strong>
        <span>
          {selectedCount} selected · {totalCount} visible
        </span>
      </div>
      <div class="toolbar__actions">
        <button type="button" class="button button--ghost" onClick={onSelectAll}>
          Select all
        </button>
        <button type="button" class="button button--ghost" onClick={onInvert}>
          Inverse
        </button>
        <button
          type="button"
          class="button button--danger"
          disabled={selectedCount === 0}
          onClick={onDelete}
        >
          Delete
        </button>
      </div>
    </div>
  )
}
