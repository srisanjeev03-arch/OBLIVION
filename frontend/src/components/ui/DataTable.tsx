import { useMemo, useState, type KeyboardEvent, type ReactNode } from 'react'
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import { cn } from '@/lib/cn'

export interface ColumnDef<T> {
  key: string
  header: ReactNode
  cell: (row: T) => ReactNode
  /** Provide to enable sorting on this column. */
  sortValue?: (row: T) => string | number | null | undefined
  width?: string
  align?: 'left' | 'right'
  mono?: boolean
}

export interface DataTableProps<T> {
  columns: readonly ColumnDef<T>[]
  rows: readonly T[]
  rowKey: (row: T) => string
  /** Accessible table description, e.g. "Operations". */
  caption: string
  onRowSelect?: (row: T) => void
  selectedKey?: string | null
  /** Rendered inside the table body when `rows` is empty — pass an EmptyState/UnavailableState. */
  emptyContent?: ReactNode
  className?: string
  dense?: boolean
}

/**
 * Compact forensic table. Rows are real focusable controls (Enter/Space select) when
 * `onRowSelect` is provided, so nothing is mouse-only.
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  onRowSelect,
  selectedKey,
  emptyContent,
  className,
  dense,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<{ key: string; dir: 'asc' | 'desc' } | null>(null)

  const sorted = useMemo(() => {
    if (!sort) return rows
    const col = columns.find((c) => c.key === sort.key)
    if (!col?.sortValue) return rows
    const getter = col.sortValue
    return [...rows].sort((a, b) => {
      const av = getter(a)
      const bv = getter(b)
      if (av == null && bv == null) return 0
      if (av == null) return 1
      if (bv == null) return -1
      const cmp =
        typeof av === 'number' && typeof bv === 'number'
          ? av - bv
          : String(av).localeCompare(String(bv))
      return sort.dir === 'asc' ? cmp : -cmp
    })
  }, [rows, sort, columns])

  const toggleSort = (key: string) => {
    setSort((prev) => {
      if (prev?.key !== key) return { key, dir: 'asc' }
      if (prev.dir === 'asc') return { key, dir: 'desc' }
      return null
    })
  }

  const handleRowKey = (e: KeyboardEvent<HTMLTableRowElement>, row: T) => {
    if (!onRowSelect) return
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onRowSelect(row)
    }
  }

  const cellPad = dense ? 'px-3 py-1.5' : 'px-3 py-2'

  return (
    <div
      className={cn('w-full overflow-x-auto rounded-md border border-line bg-surface', className)}
    >
      <table className="w-full border-collapse text-left text-[0.8125rem]">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line-strong bg-elevated/70">
            {columns.map((col) => {
              const sortable = !!col.sortValue
              const active = sort?.key === col.key
              const ariaSort = active
                ? sort.dir === 'asc'
                  ? 'ascending'
                  : 'descending'
                : sortable
                  ? 'none'
                  : undefined
              return (
                <th
                  key={col.key}
                  scope="col"
                  style={{ width: col.width }}
                  aria-sort={ariaSort}
                  className={cn(
                    'whitespace-nowrap text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-dim',
                    cellPad,
                    col.align === 'right' && 'text-right',
                  )}
                >
                  {sortable ? (
                    <button
                      type="button"
                      onClick={() => toggleSort(col.key)}
                      className={cn(
                        'inline-flex items-center gap-1 rounded-sm hover:text-fg',
                        active && 'text-fg',
                      )}
                    >
                      {col.header}
                      {active ? (
                        sort.dir === 'asc' ? (
                          <ArrowUp className="h-3 w-3" aria-hidden="true" />
                        ) : (
                          <ArrowDown className="h-3 w-3" aria-hidden="true" />
                        )
                      ) : (
                        <ArrowUpDown className="h-3 w-3 opacity-50" aria-hidden="true" />
                      )}
                    </button>
                  ) : (
                    col.header
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {sorted.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="p-0">
                {emptyContent}
              </td>
            </tr>
          ) : (
            sorted.map((row) => {
              const key = rowKey(row)
              const selected = selectedKey === key
              const interactive = !!onRowSelect
              return (
                <tr
                  key={key}
                  tabIndex={interactive ? 0 : undefined}
                  aria-selected={interactive ? selected : undefined}
                  onClick={interactive ? () => onRowSelect(row) : undefined}
                  onKeyDown={(e) => handleRowKey(e, row)}
                  className={cn(
                    'transition-colors duration-[var(--motion-duration)]',
                    interactive && 'cursor-pointer hover:bg-elevated/60 focus-visible:bg-elevated/60',
                    selected && 'bg-accent-soft',
                  )}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={cn(
                        'align-middle',
                        cellPad,
                        col.mono && 'font-mono tabular text-xs text-dim',
                        col.align === 'right' && 'text-right',
                      )}
                    >
                      {col.cell(row)}
                    </td>
                  ))}
                </tr>
              )
            })
          )}
        </tbody>
      </table>
    </div>
  )
}
