import { render } from 'preact'
import './index.css'
import { App } from './app'

const appRoot = document.getElementById('app')

if (!appRoot) {
  throw new Error('Expected #app root element')
}

render(<App />, appRoot)
