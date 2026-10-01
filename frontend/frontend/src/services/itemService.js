import api from './api';

const ITEM_MASTER_ENDPOINT = '/item-master/';

export function fetchItems({ search = '' } = {}) {
  return api
    .get(ITEM_MASTER_ENDPOINT, {
      params: {
        search: search || undefined,
        limit: 500,
      },
    })
    .then((res) =>
      res.data.filter(
        (item) => item.is_active !== false,
      ),
    );
}

export function fetchItemById(id) {
  return api
    .get(`${ITEM_MASTER_ENDPOINT}${id}`)
    .then((res) => res.data);
}

export function createItem(payload) {
  return api
    .post(ITEM_MASTER_ENDPOINT, payload)
    .then((res) => res.data);
}

export function updateItem(id, payload) {
  return api
    .patch(
      `${ITEM_MASTER_ENDPOINT}${id}`,
      payload,
    )
    .then((res) => res.data);
}

export function deleteItem(id) {
  return api
    .delete(`${ITEM_MASTER_ENDPOINT}${id}`)
    .then((res) => res.data);
}