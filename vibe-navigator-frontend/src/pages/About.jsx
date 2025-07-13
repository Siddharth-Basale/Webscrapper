import { Typography, Container } from '@mui/material';

export default function About() {
  return (
    <Container maxWidth="md">
      <Typography variant="h4" gutterBottom>
        About Vibe Navigator
      </Typography>
      <Typography paragraph>
        Discover the best places based on real user reviews from Google and Reddit.
      </Typography>
    </Container>
  );
}