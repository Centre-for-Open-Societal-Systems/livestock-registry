// The Age text for a date of birth, as the registry writes it on save
// (domain_validation_utils.format_age): "2 years, 8 months". Empty when the
// date is missing, unreadable or in the future.

const parseDate = (value: unknown): Date | null => {
    const text = String(value ?? '').trim();
    if (!text) return null;
    let match = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (match) return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    match = text.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (match) return new Date(Number(match[3]), Number(match[2]) - 1, Number(match[1]));
    return null;
};

export function formatAge(birth: unknown, today: Date = new Date()): string {
    const born = parseDate(birth);
    if (!born || Number.isNaN(born.getTime())) return '';
    let years = today.getFullYear() - born.getFullYear();
    let months = today.getMonth() - born.getMonth();
    if (today.getDate() < born.getDate()) months -= 1;
    if (months < 0) {
        years -= 1;
        months += 12;
    }
    if (years < 0) return '';
    return `${years} years, ${months} months`;
}
