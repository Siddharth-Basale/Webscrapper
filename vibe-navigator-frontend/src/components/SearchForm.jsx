import { useState } from 'react';
import { TextField, Button, Box, MenuItem, InputLabel, FormControl, Select, OutlinedInput, Chip } from '@mui/material';

const TAGS = [
  "budget-friendly", "aesthetic", "lively", "quiet", "family-friendly", "cozy", "spacious",
  "premium", "crowded", "peaceful", "healthy-options", "music", "zumba", "yoga", "late-night",
  "outdoor-seating", "fast-service", "pet-friendly", "romantic", "group-friendly", "modern",
  "traditional", "luxury", "noisy", "clean"
];

const ITEM_HEIGHT = 48;
const ITEM_PADDING_TOP = 8;
const MenuProps = {
  PaperProps: {
    style: {
      maxHeight: ITEM_HEIGHT * 6.5 + ITEM_PADDING_TOP,
      width: 250,
    },
  },
};

export default function SearchForm({ onSearch }) {
  const [city, setCity] = useState('');
  const [category, setCategory] = useState('gyms');
  const [query, setQuery] = useState('');
  const [selectedTags, setSelectedTags] = useState([]);

  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch({ city, category, query, tags: selectedTags });
  };

  return (
    <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 4 }}>
      <TextField label="City" value={city} onChange={(e) => setCity(e.target.value)} required />
      <TextField
        label="Category"
        select
        value={category}
        onChange={(e) => setCategory(e.target.value)}
      >
        <MenuItem value="gyms">Gyms</MenuItem>
        <MenuItem value="cafes">Cafes</MenuItem>
        <MenuItem value="parks">Parks</MenuItem>
      </TextField>

      <TextField
        label="Your Custom Query"
        placeholder="e.g. Best quiet cafes with healthy food"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        required
      />

      <FormControl>
        <InputLabel id="tags-label">Tags</InputLabel>
        <Select
          labelId="tags-label"
          multiple
          value={selectedTags}
          onChange={(e) => setSelectedTags(e.target.value)}
          input={<OutlinedInput label="Tags" />}
          renderValue={(selected) => (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
              {selected.map((value) => (
                <Chip key={value} label={value} />
              ))}
            </Box>
          )}
          MenuProps={MenuProps}
        >
          {TAGS.map((tag) => (
            <MenuItem key={tag} value={tag}>
              {tag}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <Button type="submit" variant="contained" size="large">
        Search
      </Button>
    </Box>
  );
}
