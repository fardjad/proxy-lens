import { render } from 'preact'
import './index.css'
import { App } from './app'

const NativeResizeObserver = window.ResizeObserver

window.ResizeObserver = class ResizeObserver extends NativeResizeObserver {
  constructor(callback: ResizeObserverCallback) {
    super((entries, observer) => {
      window.requestAnimationFrame(() => callback(entries, observer))
    })
  }
}

const appRoot = document.getElementById('app')

if (!appRoot) {
  throw new Error('Expected #app root element')
}

const storedTheme = window.localStorage.getItem('proxylens.themeMode')

if (storedTheme === 'light' || storedTheme === 'dark') {
  document.documentElement.dataset.theme = storedTheme
} else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
  document.documentElement.dataset.theme = 'dark'
}

render(<App />, appRoot)
