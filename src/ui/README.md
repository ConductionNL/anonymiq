# Anonymiq UI

A simple web frontend for the Anonymiq API. This application allows you to:

- Upload documents (PDFs)
- View document metadata and detected PII entities
- Anonymize documents by selecting which PII entities to remove
- Download anonymized documents
- Deanonymize previously anonymized documents

## Technology Stack

- React 19
- TypeScript
- Tailwind CSS
- shadcn/ui components
- React Router

## Setup

1. Install dependencies:

```bash
npm install
```

2. Start the development server:

```bash
npm run dev
```

3. Make sure the Anonymiq API is running on <http://localhost:8000>

## Building for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

## API Integration

The UI integrates with the following Anonymiq API endpoints:

- `POST /documents/upload` - Upload new documents
- `GET /documents/{file_id}/metadata` - Get document metadata and PII entities
- `POST /documents/{file_id}/anonymize` - Anonymize a document
- `GET /documents/{file_id}/download` - Download an anonymized document
- `POST /documents/deanonymize` - Deanonymize a document

## Development Notes

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default tseslint.config([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      ...tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      ...tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      ...tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default tseslint.config([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```
