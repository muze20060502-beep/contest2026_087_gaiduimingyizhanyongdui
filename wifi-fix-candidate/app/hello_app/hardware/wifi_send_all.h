#ifndef FOCUS_WIFI_SEND_ALL_H
#define FOCUS_WIFI_SEND_ALL_H

#include <errno.h>
#include <stddef.h>

/* The writer follows send(): positive progress, zero closed, -1 with errno.
 * Both HTTP headers and bodies must handle short writes.  Pacing reduces
 * bursts; the socket send-buffer limit provides TCP backpressure.
 */
static inline int wifi_send_all(void *ctx, const char *data, size_t length,
                                size_t chunk_size,
                                int (*writer)(void *, const char *, size_t),
                                void (*pause_tx)(void *))
{
  size_t sent = 0;

  if (chunk_size == 0)
    {
      errno = EINVAL;
      return -1;
    }

  while (sent < length)
    {
      size_t chunk = length - sent;
      int n;

      if (chunk > chunk_size) chunk = chunk_size;
      n = writer(ctx, data + sent, chunk);
      if (n < 0)
        {
          if (errno == EINTR) continue;
          return -1; /* Includes socket send timeout: EAGAIN/EWOULDBLOCK. */
        }
      if (n == 0)
        {
          errno = EPIPE;
          return -1;
        }
      sent += (size_t)n;
      if (sent < length && pause_tx != NULL) pause_tx(ctx);
    }
  return 0;
}

#endif
