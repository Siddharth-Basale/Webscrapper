import { Card, CardContent, Typography, Chip, Stack, Link } from '@mui/material';

export default function VibeCard({ place }) {
  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h5" gutterBottom>
          {place.name} ⭐ {place.rating} ({place.review_count} reviews)
        </Typography>
        
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {place.address}
        </Typography>
        
        <Stack direction="row" spacing={1} sx={{ my: 2 }}>
          {place.tags.map(tag => (
            <Chip key={tag} label={tag} color="primary" size="small" />
          ))}
        </Stack>
        
        <Typography variant="body1" paragraph>
          {place.summary}
        </Typography>
        
        <Typography variant="h6" gutterBottom>Key Features:</Typography>
        <ul>
          {place.key_features.map((feature, i) => (
            <li key={i}>{feature}</li>
          ))}
        </ul>
        
        <Link href={place.links.google_maps} target="_blank">
          View on Google Maps
        </Link>
      </CardContent>
    </Card>
  );
}