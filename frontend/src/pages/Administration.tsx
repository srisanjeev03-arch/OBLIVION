import { Users } from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { UnavailableState } from '@/components/states'

/**
 * Administration.
 *
 * Rendered as UNAVAILABLE rather than populated. OPENAPI.yaml publishes ten paths
 * (/api/targets*, /api/operations*, /api/recovery-objects*, /api/certificates*) and none of them
 * concern users, roles or permissions. There is therefore no backend from which to list an
 * operator, and no contract from which to derive a role assignment screen.
 *
 * The frontend's 5-role model and 24 permission keys in `@/lib/auth/types` are a provisional
 * design proposal, not a ratified contract. Showing them here as if the backend enforced them
 * would be a fabricated security control, which is worse than showing nothing.
 */
export function Administration() {
  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        title="Administration"
        purpose="User and role management."
        icon={<Users className="h-4 w-4" aria-hidden="true" />}
      />
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-2xl">
          <UnavailableState
            title="No user or role management endpoint exists in the contract"
            reason="contract/OPENAPI.yaml publishes no /api/users, /api/roles or /api/permissions path"
            description={
              <>
                Operator accounts, role assignments and permission grants are owned by the backend.
                Until those endpoints are published, this screen has nothing truthful to display, so
                it displays no accounts and no role table.
              </>
            }
          />
        </div>
      </div>
    </div>
  )
}