"use client";
// OAN: copy of upstream staff-ui (deps.json ref) components/layout/Header.tsx.
// The only change: an "Animals" link (the Animals page, SRS LR-24) for users who
// may view the register. Re-apply on top of the new upstream file when the
// deps.json ref changes.
import Image from "next/image";
import { useLocale, useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';
import Link from 'next/link';

import { ProfileDropdown, NotificationInbox, HeaderMoreMenu } from '@/components/layout';
import { useRuntimeConfig } from "@/context/RuntimeConfigContext";
import { useLogoDimensions } from '@/shared/hooks';
import Can from '@/components/shared/Can';
import { REGISTER_ACTIONS } from '@/features/shared/permissions';

export default function Header() {
    const t = useTranslations();
    const locale = useLocale();
    const { config } = useRuntimeConfig();
    const [isScrolled, setIsScrolled] = useState(false);
    const logoSrc = config?.registryLogo || "/images/common/openg2p_logo.png";
    const logoDimensions = useLogoDimensions(logoSrc);
    const isHorizontalLogo = logoDimensions?.isHorizontal ?? false;

    useEffect(() => {
        const handleScroll = () => {
            setIsScrolled(window.scrollY > 0);
        };

        window.addEventListener("scroll", handleScroll);
        return () => window.removeEventListener("scroll", handleScroll);
    }, []);

    return (
        <header className={`w-full bg-neutral-second fixed top-0 left-0 right-0 z-50 flex justify-center overflow-visible ${isScrolled ? "shadow-[0px_4px_10px_0px_rgba(0,0,0,0.15)]" : ""}`}>
            <div className="w-full h-17.5 flex items-center justify-between px-3 overflow-visible">
                <Link href={`/${locale}`} className={`flex items-center min-w-0 overflow-visible ${isHorizontalLogo ? "max-w-[min(92vw,72rem)]" : "h-full gap-2"}`}>
                    {isHorizontalLogo ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                            src={logoSrc}
                            alt="Registry Logo"
                            className="h-24 w-auto max-w-full object-contain object-left"
                        />
                    ) : (
                        <Image
                            src={logoSrc}
                            alt="Registry Logo"
                            width={40}
                            height={40}
                            className="h-10 w-10 shrink-0 object-contain"
                            unoptimized
                        />
                    )}
                    {!isHorizontalLogo && (
                        <div className="flex items-center gap-3">
                            <span
                                className="text-neutral-first text-[20px] font-medium not-italic leading-normal"
                                style={{ fontFamily: 'Roboto' }}
                            >
                                {config?.registryName ? t(config?.registryName) : t('registryGen2')}
                            </span>
                        </div>
                    )}
                </Link>

                {/* Desktop Navigation */}
                <div className="flex items-center gap-4">
                    {/* OAN: Animals page */}
                    <Can action={REGISTER_ACTIONS.view}>
                        <Link
                            href={`/${locale}/animals`}
                            className="text-[15px] font-medium text-neutral-first hover:opacity-70 no-underline"
                        >
                            {t.has('oan_animals') ? t('oan_animals') : 'Animals'}
                        </Link>
                    </Can>
                    <NotificationInbox />
                    <ProfileDropdown />
                    <HeaderMoreMenu />

                </div>
            </div>
        </header>
    );
}
