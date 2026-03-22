import { useMemo, useState } from 'preact/hooks'
import { classNames } from '../utils'

interface TokenInputProps {
  name: string
  label: string
  tokens: string[]
  onChange: (next: string[]) => void
  placeholder: string
  suggestions?: string[]
  inputMode?: 'text' | 'numeric'
}

function normalizeToken(value: string) {
  return value.trim()
}

export function TokenInput({
  name,
  label,
  tokens,
  onChange,
  placeholder,
  suggestions = [],
  inputMode = 'text',
}: TokenInputProps) {
  const [draft, setDraft] = useState('')
  const listId = useMemo(() => `token-suggestions-${name}`, [name])

  function commitToken(rawValue: string) {
    const value = normalizeToken(rawValue)
    if (!value) {
      return
    }

    if (tokens.includes(value)) {
      setDraft('')
      return
    }

    onChange([...tokens, value])
    setDraft('')
  }

  function removeToken(token: string) {
    onChange(tokens.filter((item) => item !== token))
  }

  return (
    <label class="field">
      <span class="field__label">{label}</span>
      <div class="token-input">
        <div class="token-input__tokens">
          {tokens.map((token) => (
            <button
              type="button"
              class="token-input__token"
              key={token}
              onClick={() => removeToken(token)}
              title={`Remove ${token}`}
            >
              <span>{token}</span>
              <span aria-hidden="true">×</span>
            </button>
          ))}
          <input
            value={draft}
            list={suggestions.length > 0 ? listId : undefined}
            inputMode={inputMode}
            placeholder={tokens.length === 0 ? placeholder : 'Add another'}
            onInput={(event) =>
              setDraft((event.currentTarget as HTMLInputElement).value)
            }
            onBlur={() => commitToken(draft)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ',') {
                event.preventDefault()
                commitToken(draft)
              }

              if (event.key === 'Backspace' && !draft && tokens.length > 0) {
                removeToken(tokens[tokens.length - 1])
              }
            }}
          />
        </div>
        <button
          type="button"
          class={classNames('button', 'button--ghost', !draft && 'button--muted')}
          onClick={() => commitToken(draft)}
        >
          Add
        </button>
      </div>
      {suggestions.length > 0 && (
        <datalist id={listId}>
          {suggestions.map((value) => (
            <option value={value} key={value} />
          ))}
        </datalist>
      )}
    </label>
  )
}
