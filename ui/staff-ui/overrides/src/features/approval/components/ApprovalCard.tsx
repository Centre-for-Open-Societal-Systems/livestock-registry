'use client';

// OAN: copy of upstream staff-ui (deps.json ref) features/approval/components/ApprovalCard.tsx.
// The only change: Approve and Reject stay disabled until the approver writes a
// message, so the record's author always learns why it was approved or rejected.
// Re-apply on top of the new upstream file when the deps.json ref changes.

import { useState } from 'react';
import Image from 'next/image';
import { useTranslations } from 'next-intl';
import { ApprovalTask } from '@/features/approval/types/approval';
import { formatDateTime } from '@/shared/utils/dateUtils';
import { useAuth } from '@/context/Authcontext';
import { useRbac } from '@/context/RbacContext';
import { VERIFICATION_CHANGE_REQUEST_ACTIONS } from '@/features/shared/permissions';
import { VERIFICATION_INTAKE_FORM_ACTIONS } from '@/features/shared/permissions';

interface Props {
    task: ApprovalTask;
    isPending: boolean;
    approvalDecisionBlocked?: boolean;
    onSubmit: (taskId: string, action: 'approve' | 'reject', comment: string) => Promise<boolean>;
    intakeForm?: boolean;
}

const MESSAGE_MAX_LENGTH = 100;

const statusClassMap: Record<string, string> = {
    open: 'text-amber-500',
    claimed: 'text-amber-500',
    completed: 'text-toast-success',
    cancelled: 'text-toast-failed',
};

function Field({
    label,
    value,
    valueClassName = 'text-neutral-first',
    multiline = false,
}: {
    label: string;
    value: string;
    valueClassName?: string;
    multiline?: boolean;
}) {
    return (
        <div className="min-w-0">
            <div className="text-[16px] leading-tight text-neutral-first/50">{label}</div>
            <div
                className={`mt-1 text-[15px] font-medium leading-snug ${
                    multiline ? 'break-words whitespace-pre-wrap' : 'truncate'
                } ${valueClassName}`}
                title={value}
            >
                {value}
            </div>
        </div>
    );
}

export default function ApprovalCard({
    task,
    isPending,
    approvalDecisionBlocked = false,
    onSubmit,
    intakeForm = false,
}: Props) {
    const t = useTranslations();
    const { user } = useAuth();
    const { can } = useRbac();
    const canAct = can(
        intakeForm
            ? VERIFICATION_INTAKE_FORM_ACTIONS.create
            : VERIFICATION_CHANGE_REQUEST_ACTIONS.create,
    );
    const [comment, setComment] = useState('');
    const [submittingAction, setSubmittingAction] = useState<'approve' | 'reject' | null>(null);

    const isCurrentUser = Boolean(user?.preferred_username && task.assignee === user.preferred_username);
    const isTaskActionable = task.status === 'open' || task.status === 'claimed';
    const assigneeDisplay = isCurrentUser
        ? (user?.name || task.assignee)
        : (task.assignee_name?.trim() || task.assignee);
    const showActionForm = isPending && canAct && isCurrentUser && isTaskActionable;
    const isInteractionDisabled = approvalDecisionBlocked || submittingAction !== null;
    // OAN: a message is required for both decisions.
    const commentMissing = comment.trim().length === 0;
    const commentRequiredText = t.has('oan_approval_message_required')
        ? t('oan_approval_message_required')
        : 'Write a message before you approve or reject.';

    const hasDecision = Boolean(task.decision_action);
    const decisionApproved = task.decision_action === 'approve';
    const displayDate = task.completed_at || task.created_at;
    const statusClass = statusClassMap[task.status.toLowerCase()] ?? 'text-neutral-first';
    const messageText = task.decision_comment?.trim() || '—';

    const handleAction = async (action: 'approve' | 'reject') => {
        if (commentMissing) return;
        setSubmittingAction(action);
        const success = await onSubmit(task.id, action, comment);
        if (success) {
            setComment('');
        }
        setSubmittingAction(null);
    };

    return (
        <div className="flex min-h-[188px] w-full flex-col rounded-[10px] bg-secondary-second p-3 sm:min-h-[220px] sm:p-4">
            <div className="flex shrink-0 items-center gap-3">
                <div className="relative h-10 w-10 shrink-0">
                    <Image
                        src="/images/common/verified_person.png"
                        alt="approver"
                        fill
                        className="rounded-full object-cover"
                    />
                </div>
                <div className="min-w-0 flex-1">
                    <div
                        className="truncate text-[18px] font-medium text-neutral-first"
                        title={assigneeDisplay}
                    >
                        {assigneeDisplay}
                    </div>
                    <div className="truncate text-[14px] text-neutral-first/50">
                        {formatDateTime(displayDate)}
                    </div>
                </div>
            </div>

            {showActionForm ? (
                <div className="mt-3 flex min-h-0 flex-1 flex-col">
                    <div className="grid grid-cols-2 gap-x-3">
                        <Field label={t('stage')} value={String(task.stage_order)} />
                        <Field
                            label={t('status')}
                            value={task.status}
                            valueClassName={`capitalize ${statusClass}`}
                        />
                    </div>

                    <div className="mt-2 pt-1 text-left">
                        <div className="mb-1 text-[16px] leading-tight text-neutral-first/50">{t('message')}</div>
                        <textarea
                            value={comment}
                            onChange={(e) => setComment(e.target.value.slice(0, MESSAGE_MAX_LENGTH))}
                            maxLength={MESSAGE_MAX_LENGTH}
                            rows={3}
                            placeholder={t('type_your_message')}
                            disabled={isInteractionDisabled}
                            readOnly={approvalDecisionBlocked}
                            className="min-h-[4.25rem] w-full resize-none rounded-[8px] border border-black/20 bg-white p-2 text-left text-[16px] leading-snug break-words focus:outline-none disabled:cursor-not-allowed disabled:bg-white disabled:opacity-50"
                        />
                        <div className="mt-1 text-left text-[12px] text-neutral-first/40">
                            {comment.length}/{MESSAGE_MAX_LENGTH}
                        </div>
                        {commentMissing && !approvalDecisionBlocked && (
                            <div className="mt-1 text-left text-[12px] text-toast-failed">{commentRequiredText}</div>
                        )}
                        <div className="mt-2 flex items-center justify-end gap-2">
                            <button
                                type="button"
                                disabled={isInteractionDisabled || commentMissing}
                                onClick={() => handleAction('reject')}
                                className="rounded-[8px] bg-neutral-second px-4 py-1.5 text-[14px] font-medium text-neutral-first/50 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                {submittingAction === 'reject' ? t('loading') : t('reject')}
                            </button>
                            <button
                                type="button"
                                disabled={isInteractionDisabled || commentMissing}
                                onClick={() => handleAction('approve')}
                                className="rounded-[8px] bg-neutral-first px-4 py-1.5 text-[14px] font-medium text-neutral-second disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                {submittingAction === 'approve' ? t('loading') : t('approve')}
                            </button>
                        </div>
                    </div>
                </div>
            ) : (
                <div className="mt-3 flex min-h-0 flex-1 flex-col">
                    <div className="grid grid-cols-3 gap-x-3">
                        <Field label={t('stage')} value={String(task.stage_order)} />
                        <Field
                            label={t('status')}
                            value={task.status}
                            valueClassName={`capitalize ${statusClass}`}
                        />
                        {hasDecision && (
                            <Field
                                label={t('action')}
                                value={decisionApproved ? t('approve') : t('reject')}
                                valueClassName={
                                    decisionApproved ? 'text-toast-success' : 'text-toast-failed'
                                }
                            />
                        )}
                    </div>

                    {(task.decision_comment || hasDecision) && (
                        <div className="mt-2 pt-1 text-left">
                            <Field label={t('message')} value={messageText} multiline />
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
