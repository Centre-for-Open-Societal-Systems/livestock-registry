"use client";

// OAN: copy of upstream staff-ui (deps.json ref) components/ui/StatsCard.tsx.
// The only change: the register rows and the register card lead to the register
// only for a user who may view it (register:view). Field officers and approvers
// saw "12 Livestock records" as a link and got 403 Access Denied on click; they
// now see the count without the link.
// Re-apply on top of the new upstream file when the deps.json ref changes.

import { useMemo } from "react";
import { useRbac } from "@/context/RbacContext";
import { REGISTER_ACTIONS } from "@/features/shared/permissions";
import { useFetch } from "@/shared/hooks/useFetch";
import { useTranslations } from 'next-intl';
import { Link } from '@/i18n/navigation';
import Image from "next/image";

interface StatsCardProps {
    stats_endpoint: string;
    active?: boolean;
    onSelect?: () => void;
    onNavigate?: () => void;
}

type StatsRow = {
    id: string;
    label: string;
    value: string | number;
    imageUrl?: string;
    href?: string;
};

const StatsCard = ({
    stats_endpoint,
    active = false,
    onSelect,
    onNavigate,
}: StatsCardProps) => {
    const t = useTranslations();
    // OAN: register links only with register:view.
    const { can } = useRbac();
    const canViewRegisters = can(REGISTER_ACTIONS.view);
    const isMessagesCard = stats_endpoint.includes("messages");
    const { data, loading, error } = useFetch<any>({
        url: stats_endpoint,
        enabled: !!stats_endpoint,
    });
    const { data: outgoingMessages, loading: outgoingLoading } = useFetch<any>({
        url: "/api/stats/outgoing-messages",
        enabled: isMessagesCard,
    });
    const incomingMessages = isMessagesCard ? data : null;
    const cardLoading = loading || (isMessagesCard && outgoingLoading);

    const { title, rows } = useMemo((): { title: string; rows: StatsRow[] } => {
        if (!data) return { title: t('items'), rows: [] };

        if (Array.isArray(data)) {
            return {
                title: t('dashboard_registers'),
                rows: data.slice(0, 2).map((item) => ({
                    id: item.register_id,
                    label: t(item.register_subject),
                    value: item.total_record_count,
                    imageUrl: item.register_icon?.startsWith('data:') ? item.register_icon : undefined,
                    href: item.register_mnemonic && canViewRegisters
                        ? `/register/${String(item.register_mnemonic).toLowerCase()}`
                        : undefined,
                })),
            };
        }

        if (stats_endpoint.includes("change")) {
            return {
                title: t('change_requests'),
                rows: [
                    {
                        id: "approved",
                        label: t('approved'),
                        value: data.approved_count,
                        imageUrl: "/images/register/statsIcon/approved.png",
                    },
                    {
                        id: "pending",
                        label: t('pending'),
                        value: data.pending_count,
                        imageUrl: "/images/register/statsIcon/pending.png",
                    },
                ],
            };
        }

        if (stats_endpoint.includes("intake")) {
            return {
                title: t('form_submissions'),
                rows: [
                    {
                        id: "pendingSubmissions",
                        label: t('pending_submissions'),
                        value: data.total_approval_pending_submissions,
                        imageUrl: "/images/register/statsIcon/topics.png",
                    },
                    {
                        id: "draftSubmissions",
                        label: t('draft_submissions'),
                        value: data.total_draft_submissions,
                        imageUrl: "/images/register/statsIcon/data_models.png",
                    },
                ],
            };
        }

        if (stats_endpoint.includes("messages")) {
            return {
                title: t('messages'),
                rows: [
                    {
                        id: "incomingMessages",
                        label: t('incoming_messages'),
                        value: incomingMessages.no_of_messages || "0",
                        imageUrl: "/images/messages/message_icon.png",
                        href: "/incoming-messages",
                    },
                    {
                        id: "outgoingMessages",
                        label: t('outgoing_messages'),
                        value: outgoingMessages?.no_of_messages || "0",
                        imageUrl: "/images/messages/message_icon.png",
                        href: "/outgoing-messages",
                    },
                ],
            };
        }

        if (stats_endpoint.includes("/tasks")) {
            return {
                title: t('approval_tasks'),
                rows: [
                    {
                        id: "change_request",
                        label: t('change_requests'),
                        value: data.change_request_count,
                        imageUrl: "/images/register/statsIcon/pending.png",
                        href: "/tasks/change-request",
                    },
                    {
                        id: "intake_form",
                        label: t('form_submissions'),
                        value: data.intake_form_count,
                        imageUrl: "/images/register/statsIcon/topics.png",
                        href: "/tasks/intake-form",
                    },
                ],
            };
        }

        return { title: t('items'), rows: [] };
    }, [canViewRegisters, data, incomingMessages, outgoingMessages, stats_endpoint, t]);

    const totalCount = useMemo(() => {
        // For registers, just count how many registers
        if (stats_endpoint.includes("register")) {
            return data?.length || 0;
        }
        if (stats_endpoint.includes("change")) {
            return data?.total_count || 0;
        }
        if (stats_endpoint.includes("intake")) {
            return data?.total_submissions || 0;
        }
        if (stats_endpoint.includes("messages")) {
            return (incomingMessages?.no_of_messages || 0) + (outgoingMessages?.no_of_messages || 0);
        }
        if (stats_endpoint.includes("/tasks")) {
            return data?.total || 0;
        }
    }, [data, incomingMessages, outgoingMessages, stats_endpoint]);

    const handleCardActivate = () => {
        if (cardLoading) return;
        if (active) {
            // OAN: the registers card (its data is the register list) opens a register.
            if (Array.isArray(data) && !canViewRegisters) return;
            onNavigate?.();
            return;
        }
        onSelect?.();
    };

    const handleCardClick = (event: React.MouseEvent<HTMLDivElement>) => {
        if ((event.target as HTMLElement).closest("a")) return;
        handleCardActivate();
    };

    const handleCardKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
        if (event.target !== event.currentTarget) return;
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            handleCardActivate();
        }
    };

    const rowContent = (row: StatsRow) => (
        <>
            {row.imageUrl && (
                <Image
                    src={row.imageUrl}
                    width={20}
                    height={20}
                    alt=""
                    className={active ? "invert" : "opacity-60"}
                />
            )}

            {/* value */}
            <span className="font-roboto text-[16px] font-bold leading-7 truncate overflow-hidden whitespace-nowrap" title={String(row.value)}>
                {row.value}
            </span>

            {/* label */}
            <span className="font-roboto text-[16px] font-medium leading-7 opacity-80 truncate overflow-hidden whitespace-nowrap" title={row.label}>
                {row.label}
            </span>
        </>
    );

    return (
        <div
            role="button"
            tabIndex={0}
            onClick={handleCardClick}
            onKeyDown={handleCardKeyDown}
            className={`flex flex-col justify-between transition-all duration-200 w-full rounded-[10px] px-7 py-6 cursor-pointer ${active ? "border-black bg-neutral-first text-neutral-second" : "bg-secondary-second text-secondary-third"}`}
        >
            <div className="min-h-40">
                {/* count and title */}
                <div className="mb-4 mt-4">
                    {cardLoading ? (
                        <div className="animate-pulse space-y-2">
                            <div className="h-12.5 w-32 rounded bg-secondary-third dark:bg-secondary-second-700"></div>
                            <div className="h-7 w-24 rounded bg-secondary-third dark:bg-secondary-second-700"></div>
                        </div>
                    ) : (
                        <>
                            <h2 className="font-roboto text-[45px] font-bold leading-none truncate overflow-hidden whitespace-nowrap" title={String(totalCount ?? "")}>
                                {totalCount}
                            </h2>
                            <h3 className="font-roboto text-[22px] font-bold leading-7 truncate overflow-hidden whitespace-nowrap" title={title}>
                                {title}
                            </h3>
                        </>
                    )}
                </div>


                {cardLoading ? (
                    <div className="animate-pulse">
                        <div className="h-4 w-24 rounded bg-secondary-third dark:bg-secondary-second-700 mb-1.75"></div>
                        <div className="h-5 w-32 rounded bg-secondary-third dark:bg-secondary-second-700"></div>
                    </div>
                ) : error ? (
                    <p className="text-sm text-toast-failed">{t('failed_to_load')}</p>
                ) : (
                    // items
                    <ul>
                        {rows.map((row) => (
                            <li key={row.id}>
                                {row.href ? (
                                    <Link
                                        href={row.href}
                                        onClick={(event) => event.stopPropagation()}
                                        className="flex items-center gap-2 cursor-pointer no-underline"
                                    >
                                        {rowContent(row)}
                                    </Link>
                                ) : (
                                    <div className="flex items-center gap-2">
                                        {rowContent(row)}
                                    </div>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
};

export default StatsCard;
