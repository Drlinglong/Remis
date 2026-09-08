import { useCallback, useEffect, useMemo, useState } from 'react';

export const JUDGMENT_TIERS = ['A', 'B', 'C'];

const candidateMatches = (candidate, query) => {
    if (!query) return true;
    const searchable = `${candidate.original || ''}\n${candidate.suggestion || ''}`.toLocaleLowerCase();
    return searchable.includes(query.toLocaleLowerCase());
};

export const useJudgmentCourtPresentation = ({
    batchSelectedIds,
    candidates,
    onSelectCandidate,
    selectedId,
    updateBatchSelectedIds,
}) => {
    const [viewMode, setViewMode] = useState('detail');
    const [tierFilter, setTierFilterState] = useState('all');
    const [searchQuery, setSearchQueryState] = useState('');
    const [collapsedTiers, setCollapsedTiers] = useState(() => new Set(['C']));
    const [detailFocusRequest, setDetailFocusRequest] = useState(0);

    const visibleCandidates = useMemo(() => {
        const query = searchQuery.trim();
        return candidates.filter((candidate) => (
            (tierFilter === 'all' || candidate.tier === tierFilter)
            && candidateMatches(candidate, query)
        ));
    }, [candidates, searchQuery, tierFilter]);

    const groupedCandidates = useMemo(() => {
        const grouped = { A: [], B: [], C: [] };
        visibleCandidates.forEach((candidate) => grouped[candidate.tier].push(candidate));
        return grouped;
    }, [visibleCandidates]);

    const selectedCandidate = useMemo(
        () => visibleCandidates.find((candidate) => candidate.id === selectedId),
        [selectedId, visibleCandidates],
    );

    useEffect(() => {
        if (viewMode !== 'detail' || selectedCandidate) return;
        onSelectCandidate(visibleCandidates[0]?.id || null);
    }, [onSelectCandidate, selectedCandidate, viewMode, visibleCandidates]);

    const resetBatchSelection = useCallback(() => updateBatchSelectedIds([]), [updateBatchSelectedIds]);

    const setTierFilter = useCallback((tier) => {
        setTierFilterState(tier);
        resetBatchSelection();
        if (tier === 'C') {
            setCollapsedTiers((current) => {
                const next = new Set(current);
                next.delete('C');
                return next;
            });
        }
    }, [resetBatchSelection]);

    const setSearchQuery = useCallback((query) => {
        setSearchQueryState(query);
        resetBatchSelection();
        if (query.trim()) {
            setCollapsedTiers((current) => {
                const next = new Set(current);
                next.delete('C');
                return next;
            });
        }
    }, [resetBatchSelection]);

    const toggleTier = useCallback((tier) => {
        setCollapsedTiers((current) => {
            const next = new Set(current);
            if (next.has(tier)) next.delete(tier);
            else next.add(tier);
            return next;
        });
    }, []);

    const openCandidateInDetail = useCallback((candidateId) => {
        onSelectCandidate(candidateId);
        setViewMode('detail');
        setDetailFocusRequest((current) => current + 1);
    }, [onSelectCandidate]);

    const toggleAllVisibleCandidates = useCallback(() => {
        const visibleIds = visibleCandidates.map((candidate) => candidate.id);
        const allVisibleSelected = visibleIds.every((id) => batchSelectedIds.includes(id));
        updateBatchSelectedIds(allVisibleSelected ? [] : visibleIds);
    }, [batchSelectedIds, updateBatchSelectedIds, visibleCandidates]);

    return {
        collapsedTiers,
        detailFocusRequest,
        groupedCandidates,
        openCandidateInDetail,
        searchQuery,
        selectedCandidate,
        setSearchQuery,
        setTierFilter,
        setViewMode,
        tierFilter,
        toggleAllVisibleCandidates,
        toggleTier,
        viewMode,
        visibleCandidates,
    };
};
