import axios from 'axios';

const API_URL = 'http://localhost:5000/api';

export const searchPlaces = (city, category) => {
  return axios.post(`${API_URL}/search`, { city, category });
};

export const queryVibes = (query, tags = []) => {
  return axios.post(`${API_URL}/query`, { query, tags });
};