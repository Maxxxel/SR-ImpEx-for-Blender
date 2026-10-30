"""Viewport time independent of armature clip wraps; frame time for renders."""


class PreviewClock:
    def __init__(self,seconds,token,now):
        self.seconds=seconds;self.token=token;self.anchor=now
        self.playing=False;self.suspended=False

    def sample(self,seconds,token,now,rendering=False):
        if rendering:return seconds
        if self.playing:
            return self.seconds+(max(0.,now-self.anchor) if not self.suspended else 0.)
        if token!=self.token:
            self.seconds=seconds;self.token=token
        return self.seconds

    def start(self,now):
        if not self.playing:self.anchor=now;self.playing=True

    def stop(self,now,token):
        if self.playing and not self.suspended:self.seconds+=max(0.,now-self.anchor)
        self.playing=False;self.token=token;self.anchor=now

    def suspend(self,now):
        if self.playing and not self.suspended:self.seconds+=max(0.,now-self.anchor)
        self.anchor=now;self.suspended=True

    def resume(self,now):
        self.anchor=now;self.suspended=False
