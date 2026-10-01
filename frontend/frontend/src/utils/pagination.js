export function pageNumbers(page, totalPages) {
  const visible = [...new Set([1, page - 1, page, page + 1, totalPages])]
    .filter((number) => number >= 1 && number <= totalPages)
    .sort((a, b) => a - b);
  return visible.flatMap((number, index) => (
    index && number - visible[index - 1] > 1 ? ['…', number] : [number]
  ));
}

export function historyPosition(state, action) {
  switch (action.type) {
    case 'filters': return { ...state, filterKey: action.value, page: 1 };
    case 'size': return { ...state, pageSize: action.value, page: 1 };
    case 'page': return { ...state, page: action.value };
    case 'recover': return { ...state, page: Math.min(state.page, Math.max(1, action.value)) };
    default: return state;
  }
}
