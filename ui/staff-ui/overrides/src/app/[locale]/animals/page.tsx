'use client';

// OAN: every registered animal (SRS LR-24), searched by ear tag or identifier and
// filtered by species, health and vaccination status, with a bulk status update
// sent as change requests. See src/oan/animals/animals.ts.

import { useEffect, useMemo, useState } from 'react';
import { useTranslations } from 'next-intl';
import { toast } from 'react-toastify';
import { Link } from '@/i18n/navigation';
import { TopBar } from '@/components/shared';
import { useRbac } from '@/context/RbacContext';
import { CHANGE_REQUEST_ACTIONS } from '@/features/shared/permissions';
import { useFetch } from '@/shared/hooks/useFetch';
import { usePageSize, usePagination } from '@/shared/hooks';
import {
    ANIMAL_REGISTER,
    ANIMAL_TAB,
    bulkUpdate,
    holdingNumber,
    listValues,
    toAnimalRow,
    type AnimalRow,
    type ListValue,
} from '@/oan/animals/animals';

type Filters = { species: string; health_status: string; vaccination_status: string };

const NO_FILTERS: Filters = { species: '', health_status: '', vaccination_status: '' };

const selectClass =
    'h-9 rounded-[8px] border border-secondary-third bg-neutral-second px-2 text-sm text-neutral-first';
const buttonClass =
    'h-9 rounded-[8px] bg-primary-first px-4 text-sm font-medium text-white disabled:opacity-50 cursor-pointer';
const lightButtonClass =
    'h-9 rounded-[8px] border border-primary-first px-4 text-sm font-medium text-primary-second cursor-pointer';

export default function AnimalsPage() {
    const t = useTranslations();
    // A translated text when the registry has one, else the English words.
    const text = (key: string, english: string) => (t.has(key) ? t(key) : english);
    const { can } = useRbac();
    const canUpdate = can(CHANGE_REQUEST_ACTIONS.create);
    const pageSize = usePageSize();

    const [page, setPage] = useState(1);
    const [search, setSearch] = useState('');
    const [filters, setFilters] = useState<Filters>(NO_FILTERS);
    const [reload, setReload] = useState(0);
    const [lists, setLists] = useState<Record<string, ListValue[]>>({});
    const [selected, setSelected] = useState<Record<string, AnimalRow>>({});
    const [setHealth, setSetHealth] = useState('');
    const [setVaccination, setSetVaccination] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [holdings, setHoldings] = useState<Record<string, string>>({});

    useEffect(() => {
        let cancelled = false;
        Promise.all(['LIVESTOCK_SPECIES', 'LIVESTOCK_BREED', 'LIVESTOCK_SEX', 'LIVESTOCK_HEALTH_STATUS', 'LIVESTOCK_VACCINATION_STATUS']
            .map(async (code) => [code, await listValues(code)] as const))
            .then((entries) => {
                if (!cancelled) setLists(Object.fromEntries(entries));
            });
        return () => {
            cancelled = true;
        };
    }, []);

    const filterBy = useMemo(() => {
        const applied = Object.entries(filters).filter(([, value]) => value);
        return applied.length ? Object.fromEntries(applied.map(([field, value]) => [field, { eq: value }])) : '';
    }, [filters]);

    const { data, loading } = useFetch<{ records: any[]; pagination: { number_of_items: number; number_of_pages: number } }>({
        url: '/api/register/records',
        options: {
            method: 'POST',
            body: JSON.stringify({
                register_id: ANIMAL_REGISTER,
                current_page: page,
                page_size: pageSize,
                filter_by: filterBy,
                search_text: search,
                reload,
            }),
        },
    });
    const rows = useMemo(() => (data?.records || []).map(toAnimalRow), [data]);
    const totalPages = Math.max(1, data?.pagination?.number_of_pages || 1);

    // The LS number of each Livestock record on this page, read once per record.
    useEffect(() => {
        const missing = Array.from(new Set(rows.map((row) => row.link))).filter((link) => link && !(link in holdings));
        if (!missing.length) return;
        let cancelled = false;
        Promise.all(missing.map(async (link) => [link, await holdingNumber(link)] as const)).then((found) => {
            if (!cancelled) setHoldings((prev) => ({ ...prev, ...Object.fromEntries(found) }));
        });
        return () => {
            cancelled = true;
        };
    }, [rows, holdings]);
    const { pageStart, pageEnd, total } = usePagination({
        totalItems: data?.pagination?.number_of_items ?? 0,
        currentPage: page,
        pageSize,
        currentCount: rows.length,
    });

    const label = (listCode: string, code: string) => {
        const found = (lists[listCode] || []).find((v) => v.value_code === code || v.value_id === code);
        return found?.value_display || code || '-';
    };
    const options = (listCode: string, skip: string[] = []) =>
        (lists[listCode] || []).filter((v) => !skip.includes(v.value_code));

    const changeFilter = (field: keyof Filters, value: string) => {
        setFilters((prev) => ({ ...prev, [field]: value }));
        setPage(1);
    };
    const toggle = (row: AnimalRow, on: boolean) =>
        setSelected((prev) => {
            const next = { ...prev };
            if (on) next[row.id] = row;
            else delete next[row.id];
            return next;
        });
    const allOnPage = rows.length > 0 && rows.every((row) => selected[row.id]);
    const picked = Object.values(selected);

    const apply = async () => {
        if (!picked.length || (!setHealth && !setVaccination)) return;
        const what = [
            setHealth && `${text('health_status', 'Health Status')}: ${label('LIVESTOCK_HEALTH_STATUS', setHealth)}`,
            setVaccination && `${text('vaccination_status', 'Vaccination Status')}: ${label('LIVESTOCK_VACCINATION_STATUS', setVaccination)}`,
        ].filter(Boolean).join('\n');
        if (!window.confirm(`${text('oan_animals_confirm', 'Update the selected animals?')} (${picked.length})\n\n${what}\n\n`
            + text('oan_animals_confirm_note', 'Deceased animals are skipped. The change is sent for approval and applies once approved.'))) {
            return;
        }
        setSubmitting(true);
        const result = await bulkUpdate(picked, {
            ...(setHealth ? { health_status: setHealth } : {}),
            ...(setVaccination ? { vaccination_status: setVaccination } : {}),
        });
        setSubmitting(false);
        if (result.requests) {
            toast.success(`${text('oan_animals_sent', 'Sent for approval')}: ${result.animals} / ${result.requests} `
                + text('oan_animals_requests', 'change request(s)'), { position: 'top-right', autoClose: 6000 });
        }
        if (result.skipped) {
            toast.info(`${text('oan_animals_skipped', 'Deceased animals skipped')}: ${result.skipped}`, { position: 'top-right' });
        }
        for (const failure of result.failed) toast.error(failure, { position: 'top-right', autoClose: 8000 });
        setSelected({});
        setSetHealth('');
        setSetVaccination('');
        setReload((n) => n + 1);
    };

    return (
        <div className="min-h-screen mx-auto bg-secondary-first">
            <TopBar
                breadcrumb={[{ label: text('oan_animals', 'Animals') }]}
                showSearch
                searchValue={search}
                searchPlaceholder={text('oan_animals_search', 'Search ear tag or identifier')}
                onSearch={(value) => {
                    setSearch(value.trim());
                    setPage(1);
                }}
                pxClass="px-0.5"
                showFilters={false}
                showPagination
                pageStart={pageStart}
                pageEnd={pageEnd}
                total={total}
                onPrev={() => setPage((p) => Math.max(1, p - 1))}
                onNext={() => setPage((p) => Math.min(totalPages, p + 1))}
            />

            <div className="px-7.5 space-y-3 pb-8">
                <div className="flex flex-wrap items-center gap-2">
                    <select aria-label="species" className={selectClass} value={filters.species}
                        onChange={(e) => changeFilter('species', e.target.value)}>
                        <option value="">{text('oan_animals_all_species', 'All species')}</option>
                        {options('LIVESTOCK_SPECIES').map((v) => <option key={v.value_code} value={v.value_code}>{v.value_display}</option>)}
                    </select>
                    <select aria-label="health_status" className={selectClass} value={filters.health_status}
                        onChange={(e) => changeFilter('health_status', e.target.value)}>
                        <option value="">{text('oan_animals_all_health', 'All health statuses')}</option>
                        {options('LIVESTOCK_HEALTH_STATUS').map((v) => <option key={v.value_code} value={v.value_code}>{v.value_display}</option>)}
                    </select>
                    <select aria-label="vaccination_status" className={selectClass} value={filters.vaccination_status}
                        onChange={(e) => changeFilter('vaccination_status', e.target.value)}>
                        <option value="">{text('oan_animals_all_vaccination', 'All vaccination statuses')}</option>
                        {options('LIVESTOCK_VACCINATION_STATUS').map((v) => <option key={v.value_code} value={v.value_code}>{v.value_display}</option>)}
                    </select>
                    {(filters.species || filters.health_status || filters.vaccination_status) && (
                        <button type="button" className={lightButtonClass} onClick={() => { setFilters(NO_FILTERS); setPage(1); }}>
                            {text('clear_all', 'Clear all')}
                        </button>
                    )}
                </div>

                {canUpdate && (
                    <div className="flex flex-wrap items-center gap-2 rounded-[10px] bg-neutral-second px-3 py-2">
                        <span className="text-sm font-semibold text-neutral-first mr-2">
                            {picked.length} {text('oan_animals_selected', 'selected')}
                        </span>
                        <select aria-label="set_health_status" className={selectClass} value={setHealth}
                            onChange={(e) => setSetHealth(e.target.value)}>
                            <option value="">{text('oan_animals_health_no_change', 'Health Status: no change')}</option>
                            {options('LIVESTOCK_HEALTH_STATUS', ['DECEASED']).map((v) =>
                                <option key={v.value_code} value={v.value_code}>{v.value_display}</option>)}
                        </select>
                        <select aria-label="set_vaccination_status" className={selectClass} value={setVaccination}
                            onChange={(e) => setSetVaccination(e.target.value)}>
                            <option value="">{text('oan_animals_vaccination_no_change', 'Vaccination Status: no change')}</option>
                            {options('LIVESTOCK_VACCINATION_STATUS').map((v) =>
                                <option key={v.value_code} value={v.value_code}>{v.value_display}</option>)}
                        </select>
                        <button type="button" className={buttonClass} onClick={apply}
                            disabled={submitting || !picked.length || (!setHealth && !setVaccination)}>
                            {submitting ? text('oan_animals_sending', 'Sending…') : text('oan_animals_apply', 'Apply to selected')}
                        </button>
                        {picked.length > 0 && (
                            <button type="button" className={lightButtonClass} onClick={() => setSelected({})}>
                                {text('oan_animals_clear_selection', 'Clear selection')}
                            </button>
                        )}
                    </div>
                )}

                <div className="overflow-x-auto rounded-[10px] bg-neutral-second">
                    <table className="w-full text-sm text-neutral-first">
                        <thead className="text-left text-secondary-third">
                            <tr>
                                {canUpdate && (
                                    <th className="p-3 w-10">
                                        <input type="checkbox" aria-label="select_page" checked={allOnPage}
                                            onChange={(e) => rows.forEach((row) => toggle(row, e.target.checked))} />
                                    </th>
                                )}
                                <th className="p-3">{text('oan_animals_identifier', 'Ear Tag / Identifier')}</th>
                                <th className="p-3">{text('species', 'Species')}</th>
                                <th className="p-3">{text('breed', 'Breed')}</th>
                                <th className="p-3">{text('sex', 'Sex')}</th>
                                <th className="p-3">{text('health_status', 'Health Status')}</th>
                                <th className="p-3">{text('vaccination_status', 'Vaccination Status')}</th>
                                <th className="p-3">{text('oan_animals_record', 'Livestock record')}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <tr><td colSpan={8} className="p-6 text-center text-secondary-third">{text('loading', 'Loading…')}</td></tr>
                            ) : rows.length === 0 ? (
                                <tr><td colSpan={8} className="p-6 text-center text-secondary-third">{text('oan_animals_none', 'No animals found')}</td></tr>
                            ) : rows.map((row) => (
                                <tr key={row.id} className="border-t border-secondary-first">
                                    {canUpdate && (
                                        <td className="p-3">
                                            <input type="checkbox" aria-label={`select_${row.tag}`} checked={!!selected[row.id]}
                                                onChange={(e) => toggle(row, e.target.checked)} />
                                        </td>
                                    )}
                                    <td className="p-3 font-medium">{row.tag || '-'}</td>
                                    <td className="p-3">{label('LIVESTOCK_SPECIES', row.species)}</td>
                                    <td className="p-3">{label('LIVESTOCK_BREED', row.breed)}</td>
                                    <td className="p-3">{label('LIVESTOCK_SEX', row.gender)}</td>
                                    <td className="p-3">{label('LIVESTOCK_HEALTH_STATUS', row.health)}</td>
                                    <td className="p-3">{label('LIVESTOCK_VACCINATION_STATUS', row.vaccination)}</td>
                                    <td className="p-3">
                                        {row.link ? (
                                            <Link className="text-primary-second underline"
                                                href={`/register/livestock/${row.link}?tab=${ANIMAL_TAB}`}>
                                                {holdings[row.link] || row.holding || text('oan_animals_open', 'Open')}
                                            </Link>
                                        ) : '-'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
