export const isProofreadingRowChanged = row => (
    row.editable && row.final_value !== row.baseline_value
);
