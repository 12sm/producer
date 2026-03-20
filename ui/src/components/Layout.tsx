import { NavLink, Outlet } from 'react-router-dom'

const links = [
  { to: '/', label: 'Dashboard', icon: '⬡' },
  { to: '/vocab', label: 'Vocabulary', icon: '◈' },
  { to: '/bank', label: 'Snippet Bank', icon: '▤' },
]

export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col sm:flex-row">
      {/* Sidebar — hidden on mobile */}
      <nav className="hidden sm:flex w-52 shrink-0 bg-surface border-r border-border flex-col p-4 gap-1">
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
      <main className="flex-1 p-4 sm:p-6 overflow-auto pb-20 sm:pb-6">
        <Outlet />
      </main>

      {/* Bottom tab bar — mobile only */}
      <nav className="sm:hidden fixed bottom-0 left-0 right-0 bg-surface border-t border-border flex z-50">
        {links.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex-1 flex flex-col items-center justify-center py-3 gap-0.5 text-xs transition-colors ${
                isActive ? 'text-accent' : 'text-text-muted'
              }`
            }
          >
            <span className="text-base leading-none">{icon}</span>
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
