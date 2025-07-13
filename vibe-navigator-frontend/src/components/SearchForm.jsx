import { useState } from 'react';
import { TextField, Button, Box } from '@mui/material';

export default function SearchForm({ onSearch }) {
  const [city, setCity] = useState('');
  const [category, setCategory] = useState('gyms');

  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch({ city, category });
  };

  return (
    <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', gap: 2, mb: 4 }}>
      <TextField 
        label="City" 
        value={city} 
        onChange={(e) => setCity(e.target.value)} 
        required 
      />
      <TextField
        label="Category"
        select
        value={category}
        onChange={(e) => setCategory(e.target.value)}
        SelectProps={{ native: true }}
      >
        <option value="gyms">Gyms</option>
        <option value="cafes">Cafes</option>
        <option value="parks">Parks</option>
      </TextField>
      <Button type="submit" variant="contained" size="large">
        Search
      </Button>
    </Box>
  );
}