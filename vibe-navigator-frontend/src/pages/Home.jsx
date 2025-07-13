import { useState } from 'react';
import { Container, Typography } from '@mui/material';
import SearchForm from '../components/SearchForm';
import ResultsList from '../components/ResultsList';
import axios from 'axios';

export default function Home() {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async ({ city, category, query, tags }) => {
    setLoading(true);
    try {
      // First: collect data
      await axios.post('http://localhost:5000/api/search', { city, category });

      // Then: query using user-defined query + selected tags
      const { data } = await axios.post('http://localhost:5000/api/query', {
        query,
        tags
      });

      setResults([data]);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="md">
      <Typography variant="h3" component="h1" gutterBottom>
        Vibe Navigator
      </Typography>
      <Typography variant="subtitle1" gutterBottom>
        Discover places based on user reviews
      </Typography>

      <SearchForm onSearch={handleSearch} />

      {loading ? (
        <Typography>Loading recommendations...</Typography>
      ) : (
        <ResultsList results={results} />
      )}
    </Container>
  );
}
