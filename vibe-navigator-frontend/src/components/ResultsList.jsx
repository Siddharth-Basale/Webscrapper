import { Box } from '@mui/material';
import VibeCard from './VibeCard';

export default function ResultsList({ results }) {
  return (
    <Box>
      {results.map((place, index) => (
        <VibeCard key={index} place={place} />
      ))}
    </Box>
  );
}