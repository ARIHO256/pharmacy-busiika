# Frontend npm setup

The old generated `package-lock.json` was incomplete and contained dependency entries without versions. It was removed intentionally.

Run the first clean installation with:

```bash
rm -rf node_modules package-lock.json
npm cache verify
npm install
npm run build
npm run dev
```

The first successful `npm install` creates a new valid `package-lock.json`. Commit that new lock file to source control.

Expected local addresses:

- React/Vite: http://localhost:3000
- Django API: http://localhost:4000

If npm is configured to use an unavailable mirror, inspect it with:

```bash
npm config get registry
```

For a normal public npm installation, use:

```bash
npm config set registry https://registry.npmjs.org/
```
