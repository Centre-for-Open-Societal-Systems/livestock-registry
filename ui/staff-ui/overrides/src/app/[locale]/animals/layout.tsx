// OAN: the Animals page (SRS LR-24) is for users who may view the register.

import RequireAction from "@/components/shared/RequireAction";
import { REGISTER_ACTIONS } from "@/features/shared/permissions";

export default function AnimalsLayout({ children }: { children: React.ReactNode }) {
    return (
        <RequireAction action={REGISTER_ACTIONS.view}>
            {children}
        </RequireAction>
    );
}
