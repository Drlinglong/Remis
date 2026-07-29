const initialState = {
  activeTab: 'dashboard',
  selectedProject: null,
};

let reviewSessionState = { ...initialState };

export const getNeologismReviewSession = () => reviewSessionState;

export const updateNeologismReviewSession = (patch) => {
  reviewSessionState = {
    ...reviewSessionState,
    ...patch,
  };
};

export const resetNeologismReviewSessionForTests = () => {
  reviewSessionState = { ...initialState };
};
