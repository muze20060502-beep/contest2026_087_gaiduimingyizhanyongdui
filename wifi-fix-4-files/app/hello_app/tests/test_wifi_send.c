#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../hardware/wifi_send_all.h"

struct sink
{
  char bytes[100000];
  size_t used;
  size_t max_write;
  int calls;
  int pauses;
  int interrupt_first;
  int fail_after;
  int failure;
};

static int write_fake(void *ctx, const char *data, size_t length)
{
  struct sink *s = ctx;
  s->calls++;
  assert(length <= 2048);
  if (s->interrupt_first && s->calls == 1)
    {
      errno = EINTR;
      return -1;
    }
  if (s->fail_after && s->calls >= s->fail_after)
    {
      errno = s->failure;
      return s->failure ? -1 : 0;
    }
  if (length > s->max_write) length = s->max_write;
  assert(s->used + length <= sizeof(s->bytes));
  memcpy(s->bytes + s->used, data, length);
  s->used += length;
  return (int)length;
}

static void pause_fake(void *ctx)
{
  ((struct sink *)ctx)->pauses++;
}

int main(void)
{
  static char body[90000];
  static struct sink s;
  const char header[] = "POST /test HTTP/1.1\r\nContent-Length: 90000\r\n\r\n";
  size_t i;
  for (i = 0; i < sizeof(body); i++) body[i] = (char)('A' + i % 26);

  /* A short header write must not discard the rest of the header. */
  s.max_write = 7;
  s.interrupt_first = 1;
  assert(wifi_send_all(&s, header, strlen(header), 2048,
                        write_fake, pause_fake) == 0);
  s.max_write = 113;
  assert(wifi_send_all(&s, body, sizeof(body), 2048,
                        write_fake, pause_fake) == 0);
  assert(s.used == strlen(header) + sizeof(body));
  assert(memcmp(s.bytes, header, strlen(header)) == 0);
  assert(memcmp(s.bytes + strlen(header), body, sizeof(body)) == 0);
  assert(s.pauses > 0);

  memset(&s, 0, sizeof(s));
  s.max_write = 2048;
  s.fail_after = 2;
  s.failure = EAGAIN;
  assert(wifi_send_all(&s, body, sizeof(body), 2048,
                        write_fake, pause_fake) == -1);
  assert(errno == EAGAIN && s.calls == 2 && s.used == 2048);

  memset(&s, 0, sizeof(s));
  s.fail_after = 1;
  assert(wifi_send_all(&s, body, sizeof(body), 2048,
                        write_fake, pause_fake) == -1);
  assert(errno == EPIPE && s.calls == 1);

  memset(&s, 0, sizeof(s));
  s.fail_after = 1;
  s.failure = ECONNRESET;
  assert(wifi_send_all(&s, body, sizeof(body), 2048,
                        write_fake, pause_fake) == -1);
  assert(errno == ECONNRESET && s.calls == 1);
  assert(wifi_send_all(&s, body, 0, 2048,
                        write_fake, pause_fake) == 0);
  assert(s.calls == 1);
  puts("wifi send tests passed: short writes, EINTR, 90KB body, timeout, close, reset, empty body");
  return 0;
}
