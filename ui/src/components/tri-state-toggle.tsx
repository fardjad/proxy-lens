import type { TriState } from '../types'
import { classNames } from '../utils'

interface TriStateToggleProps {
  label: string
  value: TriState
  onChange: (value: TriState) => void
}

const OPTIONS: Array<{ label: string; value: TriState }> = [
  { label: 'Any', value: undefined },
  { label: 'Yes', value: true },
  { label: 'No', value: false },
]

export function TriStateToggle({
  label,
  value,
  onChange,
}: TriStateToggleProps) {
  return (
    <div class="field">
      <span class="field__label">{label}</span>
      <div class="segmented">
        {OPTIONS.map((option) => {
          const isActive = option.value === value

          return (
            <button
              type="button"
              key={option.label}
              class={classNames('segmented__option', isActive && 'is-active')}
              onClick={() => onChange(option.value)}
            >
              {option.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
