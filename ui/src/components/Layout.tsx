import { NavLink, Outlet } from 'react-router-dom'

const links = [
  { to: '/', label: 'Dashboard' },
  { to: '/vocab', label: 'Vocabulary' },
  { to: '/bank', label: 'Snippet Bank' },
]

export default function Layout() {
  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <nav className="w-52 shrink-0 bg-surface border-r border-border flex flex-col p-4 gap-1">
        <h1 className="text-accent font-bold text-lg mb-6 tracking-tight">
          Producer Lab
        </h1>

        {links.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `px-3 py-2 rounded text-sm transition-colors ${
                isActive
                  ? 'bg-accent-dim text-accent'
                  : 'text-text-muted hover:text-text hover:bg-surface-2'
              }`
            }
          >
            {label}
          </NavLink>
        ))}

        <div className="mt-auto text-xs text-text-muted pt-4 border-t border-border">
          Bracket Prompt Lab
        </div>
      </nav>

      {/* Content */}
      <main className="flex-1 p-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
