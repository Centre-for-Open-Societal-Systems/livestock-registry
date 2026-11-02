// Inside a dialog-table pop-up the platform keeps each field's value in the
// widget store under "<table widget-id>-dlg-<session>-<column-key>". A widget
// reaches the other columns of the same row by swapping its column key.
// Outside a dialog (no "-dlg-" or a different key) there is no sibling: null.
export function dialogSiblingId(widgetId: string, columnKey: unknown, otherKey: string): string | null {
    const key = String(columnKey || '');
    if (!key || !widgetId.includes('-dlg-') || !widgetId.endsWith(key)) return null;
    return widgetId.slice(0, widgetId.length - key.length) + otherKey;
}
