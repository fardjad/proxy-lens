import '@testing-library/jest-dom'

if (!('createObjectURL' in URL)) {
  Object.defineProperty(URL, 'createObjectURL', {
    value: () => 'blob:mock',
  })
}

if (!('revokeObjectURL' in URL)) {
  Object.defineProperty(URL, 'revokeObjectURL', {
    value: () => {},
  })
}
