# Fiche Cuisine Manager - Design System Documentation

## Overview

Modern, professional, accessible design system for restaurant management application. Inspired by industry-leading SaaS dashboards (Linear, Vercel, Stripe) with a distinctive violet/plum brand identity.

---

## Design Philosophy

### Core Principles

1. **Clarity First**: Information hierarchy optimized for quick scanning and decision-making
2. **Consistency**: Unified visual language across all components and states
3. **Accessibility**: WCAG 2.1 AA compliant, keyboard navigable, screen reader friendly
4. **Performance**: Lightweight, optimized for fast loading and smooth interactions
5. **Responsive**: Seamless experience from mobile to desktop

### Visual Identity

- **Brand**: Elegant violet/plum palette reflecting restaurant sophistication
- **Tone**: Professional, trustworthy, efficient
- **Style**: Clean, modern, minimal with purposeful details

---

## Design Tokens

### Color System

#### Brand Colors
```css
--brand-primary: #693381      /* Main brand violet */
--brand-primary-hover: #7d3d99
--brand-primary-active: #5a2a6e
--brand-secondary: #422052    /* Deep plum */
--brand-accent: #9361a6       /* Light violet */
```

#### Neutral Palette
```css
--neutral-50: #fafafa   /* Lightest background */
--neutral-100: #f5f5f5  /* Subtle background */
--neutral-200: #e5e5e5  /* Border default */
--neutral-300: #d4d4d4  /* Border strong */
--neutral-400: #a3a3a3  /* Disabled text */
--neutral-500: #737373  /* Tertiary text */
--neutral-600: #525252  /* Secondary text */
--neutral-700: #404040  /* Body text */
--neutral-800: #262626  /* Headings */
--neutral-900: #171717  /* Primary text */
```

#### Semantic Colors
```css
--success: #10b981      /* Green - success states */
--warning: #f59e0b      /* Amber - warnings */
--error: #ef4444        /* Red - errors */
--info: #3b82f6         /* Blue - information */
```

### Typography

#### Font Families
```css
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif
--font-mono: 'SF Mono', 'Roboto Mono', 'Courier New', monospace
```

#### Font Sizes
```css
--text-xs: 0.75rem      /* 12px - captions, labels */
--text-sm: 0.875rem     /* 14px - body text, buttons */
--text-base: 1rem       /* 16px - default body */
--text-lg: 1.125rem     /* 18px - card titles */
--text-xl: 1.25rem      /* 20px - section headers */
--text-2xl: 1.5rem      /* 24px - page titles */
--text-3xl: 1.875rem    /* 30px - hero text */
```

#### Font Weights
```css
--weight-normal: 400    /* Body text */
--weight-medium: 500    /* Emphasis */
--weight-semibold: 600  /* Headings, buttons */
--weight-bold: 700      /* Strong emphasis */
```

#### Line Heights
```css
--leading-tight: 1.25   /* Headings */
--leading-normal: 1.5   /* Body text */
--leading-relaxed: 1.75 /* Long-form content */
```

### Spacing System

Based on 4px grid for mathematical consistency:

```css
--space-1: 0.25rem   /* 4px */
--space-2: 0.5rem    /* 8px */
--space-3: 0.75rem   /* 12px */
--space-4: 1rem      /* 16px */
--space-5: 1.25rem   /* 20px */
--space-6: 1.5rem    /* 24px */
--space-8: 2rem      /* 32px */
--space-10: 2.5rem   /* 40px */
--space-12: 3rem     /* 48px */
--space-16: 4rem     /* 64px */
```

### Border Radius
```css
--radius-sm: 0.375rem   /* 6px - small elements */
--radius-md: 0.5rem     /* 8px - inputs, buttons */
--radius-lg: 0.75rem    /* 12px - cards */
--radius-xl: 1rem       /* 16px - large cards */
--radius-full: 9999px   /* Pills, avatars */
```

### Shadows
```css
--shadow-xs: 0 1px 2px 0 rgba(0, 0, 0, 0.05)
--shadow-sm: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)
--shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)
--shadow-brand: 0 4px 12px rgba(105, 51, 129, 0.15)
```

### Transitions
```css
--transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1)
--transition-base: 200ms cubic-bezier(0.4, 0, 0.2, 1)
--transition-slow: 300ms cubic-bezier(0.4, 0, 0.2, 1)
```

---

## Component Library

### Buttons

#### Variants

**Primary** - Main actions
```html
<button class="btn btn-primary">Enregistrer</button>
```

**Secondary** - Alternative actions
```html
<button class="btn btn-secondary">Annuler</button>
```

**Ghost** - Tertiary actions
```html
<button class="btn btn-ghost">Modifier</button>
```

**Danger** - Destructive actions
```html
<button class="btn btn-danger">Supprimer</button>
```

#### Sizes
```html
<button class="btn btn-sm">Small</button>
<button class="btn">Default</button>
<button class="btn btn-lg">Large</button>
<button class="btn btn-icon"><Icon /></button>
```

#### States
- **Default**: Normal state
- **Hover**: Slight lift + shadow increase
- **Active**: Pressed state
- **Disabled**: 50% opacity, no pointer events
- **Focus**: 2px outline for keyboard navigation

### Cards

#### Basic Card
```html
<div class="card">
  <div class="card-header">
    <h3>Card Title</h3>
  </div>
  <div class="card-body">
    Content goes here
  </div>
  <div class="card-footer">
    <button class="btn btn-primary">Action</button>
  </div>
</div>
```

#### Reservation Card (Specialized)
```html
<div class="reservation-card">
  <div class="card-header">
    <h3>Client Name</h3>
  </div>
  <div class="card-body">
    <div class="meta-list">
      <div class="meta-item">
        <CalendarIcon />
        <span>Date</span>
      </div>
    </div>
  </div>
  <div class="card-footer">
    <button class="btn btn-outline">Modifier</button>
  </div>
</div>
```

### Forms

#### Input Fields
```html
<div class="form-group">
  <label class="label label-required">Nom du client</label>
  <input type="text" class="input" placeholder="Entrez le nom" />
  <span class="help-text">Nom complet du client</span>
</div>
```

#### Input with Icon
```html
<div class="form-group">
  <label class="label">Email</label>
  <div class="input-group">
    <span class="input-group-text"><MailIcon /></span>
    <input type="email" class="input" />
  </div>
</div>
```

#### Select
```html
<select class="input">
  <option>Option 1</option>
  <option>Option 2</option>
</select>
```

#### Textarea
```html
<textarea class="input" rows="4"></textarea>
```

#### Checkbox
```html
<div class="form-check">
  <input type="checkbox" class="form-check-input" id="check1" />
  <label class="form-check-label" for="check1">Option</label>
</div>
```

### Badges & Chips

```html
<!-- Status Badge -->
<span class="badge badge-primary">Confirmé</span>
<span class="badge badge-success">Succès</span>
<span class="badge badge-warning">En attente</span>
<span class="badge badge-error">Erreur</span>

<!-- Allergen Chip -->
<div class="allergen-chip">
  <img src="icon.png" class="allergen-icon" />
  <span class="allergen-chip-label">Gluten</span>
</div>

<!-- Drink Badge -->
<span class="drink-badge">
  <WineIcon />
  <span class="drink-text">Avec alcool</span>
</span>
```

### Tables

```html
<div class="table-container">
  <table class="table">
    <thead>
      <tr>
        <th>Colonne 1</th>
        <th>Colonne 2</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Donnée 1</td>
        <td>Donnée 2</td>
      </tr>
    </tbody>
  </table>
</div>
```

---

## Layout Patterns

### App Layout
```html
<div class="app-layout app-theme">
  <aside class="sidebar">
    <div class="sidebar-header">App Name</div>
    <nav class="sidebar-nav">
      <a href="#" class="nav-link active">Item</a>
    </nav>
  </aside>
  <main class="content">
    <!-- Page content -->
  </main>
</div>
```

### Container
```html
<div class="container">
  <!-- Centered, max-width content -->
</div>
```

### Grid Layouts
```html
<!-- Two columns -->
<div class="grid grid-cols-2 gap-4">
  <div>Column 1</div>
  <div>Column 2</div>
</div>

<!-- Reservation sections -->
<div class="res-sections">
  <div class="res-col">Main content</div>
  <div class="res-col">Sidebar</div>
</div>
```

---

## Accessibility Guidelines

### Keyboard Navigation

- **Tab**: Navigate between interactive elements
- **Enter/Space**: Activate buttons and links
- **Escape**: Close modals and dropdowns
- **Arrow keys**: Navigate within menus and lists

### Focus Management

- All interactive elements have visible focus states
- Focus outline: 2px solid brand-primary with 2px offset
- Skip links for screen readers
- Logical tab order

### Screen Readers

- Semantic HTML elements (`<nav>`, `<main>`, `<aside>`)
- ARIA labels for icon-only buttons
- ARIA live regions for dynamic content
- Descriptive link text

### Color Contrast

- Text on background: minimum 4.5:1 ratio
- Large text (18px+): minimum 3:1 ratio
- Interactive elements: minimum 3:1 ratio
- All semantic colors meet WCAG AA standards

### Responsive Design

- Mobile-first approach
- Breakpoints:
  - Mobile: < 768px
  - Tablet: 768px - 1024px
  - Desktop: > 1024px
- Touch targets: minimum 44x44px
- Readable line lengths: max 80 characters

---

## Best Practices

### Component Usage

1. **Use semantic HTML**: `<button>` for buttons, `<a>` for links
2. **Combine classes**: `btn btn-primary btn-sm` for variations
3. **Maintain hierarchy**: One primary action per section
4. **Consistent spacing**: Use spacing utilities (`space-y-4`, `gap-3`)
5. **Accessibility first**: Always include labels, ARIA attributes

### Performance

1. **Minimize CSS**: Use utility classes where appropriate
2. **Optimize images**: Compress and use appropriate formats
3. **Lazy load**: Non-critical content below the fold
4. **Reduce motion**: Respect `prefers-reduced-motion`

### Maintenance

1. **Use design tokens**: Never hardcode colors or spacing
2. **Document changes**: Update this file when adding components
3. **Test thoroughly**: All states, all breakpoints, all browsers
4. **Version control**: Track design system changes separately

---

## Migration Guide

### From Old Styles

The new design system maintains backward compatibility while providing modern alternatives:

**Old** → **New**
- `.app-theme-violet` → `.app-theme` (simplified)
- Custom spacing → Design tokens (`var(--space-4)`)
- Inline styles → Utility classes
- Mixed button styles → Consistent `.btn` variants

### Gradual Adoption

1. **Phase 1**: Core layout and navigation (✅ Complete)
2. **Phase 2**: Cards and forms (✅ Complete)
3. **Phase 3**: Tables and lists (✅ Complete)
4. **Phase 4**: Specialized components (✅ Complete)

---

## Browser Support

- **Chrome/Edge**: Latest 2 versions
- **Firefox**: Latest 2 versions
- **Safari**: Latest 2 versions
- **Mobile Safari**: iOS 14+
- **Chrome Mobile**: Latest

---

## Resources

### Design References
- **Linear**: Clean, minimal SaaS dashboard
- **Vercel**: Modern developer tools UI
- **Stripe**: Professional payment interface

### Tools
- **Figma**: Design prototypes and components
- **Chrome DevTools**: Accessibility audits
- **Lighthouse**: Performance and accessibility scoring

### Further Reading
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [Inclusive Components](https://inclusive-components.design/)
- [Material Design Accessibility](https://material.io/design/usability/accessibility.html)

---

## Changelog

### v2.0.0 (2026-02-01)
- ✨ Complete design system overhaul
- ✨ Modern component library
- ✨ Comprehensive design tokens
- ✨ Enhanced accessibility
- ✨ Responsive improvements
- ✨ Performance optimizations
- 🎨 Refined violet/plum brand identity
- 📚 Complete documentation

### v1.0.0 (Initial)
- Basic violet theme
- Core components
- Functional layouts
