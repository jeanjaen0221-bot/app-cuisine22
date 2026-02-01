# Quick Start - UI/UX Design System

## Immediate Usage Guide

### Using the New Design System

All components are ready to use. Simply apply the appropriate classes:

#### Buttons
```html
<!-- Primary action -->
<button class="btn btn-primary">Enregistrer</button>

<!-- Secondary action -->
<button class="btn btn-secondary">Annuler</button>

<!-- Tertiary action -->
<button class="btn btn-ghost">Modifier</button>

<!-- Destructive action -->
<button class="btn btn-danger">Supprimer</button>

<!-- Small size -->
<button class="btn btn-primary btn-sm">Petit</button>

<!-- With icon -->
<button class="btn btn-primary">
  <PlusIcon className="w-4 h-4" />
  Ajouter
</button>
```

#### Cards
```html
<div class="card">
  <div class="card-header">
    <h3>Titre de la carte</h3>
  </div>
  <div class="card-body">
    Contenu ici
  </div>
  <div class="card-footer">
    <button class="btn btn-primary">Action</button>
  </div>
</div>
```

#### Forms
```html
<div class="form-group">
  <label class="label label-required">Nom</label>
  <input type="text" class="input" placeholder="Entrez le nom" />
  <span class="help-text">Texte d'aide</span>
</div>

<!-- With icon -->
<div class="form-group">
  <label class="label">Email</label>
  <div class="input-group">
    <span class="input-group-text">
      <MailIcon className="w-4 h-4" />
    </span>
    <input type="email" class="input" />
  </div>
</div>
```

#### Badges
```html
<span class="badge badge-primary">Confirmé</span>
<span class="badge badge-success">Succès</span>
<span class="badge badge-warning">En attente</span>
<span class="badge badge-error">Erreur</span>
```

#### Layout
```html
<!-- Spacing -->
<div class="space-y-4">
  <div>Item 1</div>
  <div>Item 2</div>
</div>

<!-- Flex -->
<div class="flex items-center justify-between gap-3">
  <div>Left</div>
  <div>Right</div>
</div>

<!-- Grid -->
<div class="grid grid-cols-2 gap-4">
  <div>Column 1</div>
  <div>Column 2</div>
</div>
```

### Design Tokens

Use CSS variables for consistency:

```css
/* Colors */
color: var(--brand-primary);
background: var(--bg-base);
border-color: var(--border-default);

/* Spacing */
padding: var(--space-4);
gap: var(--space-3);
margin-bottom: var(--space-6);

/* Typography */
font-size: var(--text-sm);
font-weight: var(--weight-semibold);
line-height: var(--leading-normal);

/* Shadows */
box-shadow: var(--shadow-sm);

/* Radius */
border-radius: var(--radius-md);

/* Transitions */
transition: all var(--transition-fast);
```

### Common Patterns

#### Action Bar
```html
<div class="flex items-center justify-between gap-3">
  <h2 class="text-xl font-semibold">Page Title</h2>
  <div class="flex gap-2">
    <button class="btn btn-secondary">Annuler</button>
    <button class="btn btn-primary">Enregistrer</button>
  </div>
</div>
```

#### Form Section
```html
<div class="card">
  <div class="card-header">
    <h3>Informations</h3>
  </div>
  <div class="card-body space-y-4">
    <div class="form-group">
      <label class="label">Champ 1</label>
      <input type="text" class="input" />
    </div>
    <div class="form-group">
      <label class="label">Champ 2</label>
      <input type="text" class="input" />
    </div>
  </div>
  <div class="card-footer">
    <button class="btn btn-primary">Enregistrer</button>
  </div>
</div>
```

#### Data Table
```html
<div class="table-container">
  <table class="table">
    <thead>
      <tr>
        <th>Colonne 1</th>
        <th>Colonne 2</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Donnée 1</td>
        <td>Donnée 2</td>
        <td>
          <button class="btn btn-ghost btn-sm">Modifier</button>
        </td>
      </tr>
    </tbody>
  </table>
</div>
```

### Responsive Utilities

```html
<!-- Hide on mobile -->
<div class="hidden md:block">Desktop only</div>

<!-- Stack on mobile, row on desktop -->
<div class="flex flex-col md:flex-row gap-4">
  <div>Item 1</div>
  <div>Item 2</div>
</div>
```

### Accessibility Checklist

✅ **Every button** needs accessible text or aria-label
✅ **Every form input** needs a label
✅ **Every image** needs alt text
✅ **Interactive elements** must be keyboard accessible
✅ **Focus states** are visible by default

```html
<!-- Good -->
<button class="btn btn-primary" aria-label="Ajouter une réservation">
  <PlusIcon className="w-4 h-4" />
</button>

<!-- Good -->
<label class="label" for="client-name">Nom du client</label>
<input id="client-name" type="text" class="input" />
```

### Color Usage

**Brand Colors** - Actions, links, emphasis
```html
<button class="btn btn-primary">Primary action</button>
<a href="#" class="text-brand">Link</a>
```

**Semantic Colors** - Status, feedback
```html
<span class="badge badge-success">Succès</span>
<span class="badge badge-error">Erreur</span>
<span class="badge badge-warning">Attention</span>
```

**Neutral Colors** - Text, backgrounds, borders
```html
<div class="bg-base border border-default">
  <p class="text-primary">Primary text</p>
  <p class="text-secondary">Secondary text</p>
  <p class="text-tertiary">Tertiary text</p>
</div>
```

### Common Mistakes to Avoid

❌ **Don't hardcode colors**
```css
/* Bad */
color: #693381;

/* Good */
color: var(--brand-primary);
```

❌ **Don't use arbitrary spacing**
```css
/* Bad */
margin: 17px;

/* Good */
margin: var(--space-4);
```

❌ **Don't skip accessibility**
```html
<!-- Bad -->
<button><Icon /></button>

<!-- Good -->
<button aria-label="Delete">
  <Icon />
</button>
```

❌ **Don't mix old and new patterns**
```html
<!-- Bad -->
<div class="app-theme-violet">

<!-- Good -->
<div class="app-theme">
```

### Testing Your Changes

1. **Visual Check**: Does it look consistent?
2. **Responsive Check**: Test mobile, tablet, desktop
3. **Keyboard Check**: Can you navigate with Tab?
4. **Screen Reader Check**: Are labels present?
5. **Contrast Check**: Use browser DevTools

### Getting Help

- **Design System Docs**: See `DESIGN_SYSTEM.md`
- **Component Examples**: Check existing pages
- **Token Reference**: See `design-system.css`
- **Delivery Report**: See `UI_UX_DELIVERY.md`

---

**Remember**: The design system is here to help you build faster and more consistently. When in doubt, follow existing patterns!
