/**
 * Resolves a Fly.pl search URL for rolling monitors so that date parameters
 * (startDateMin, startDateMax, returnDate) are always dynamic and point to the
 * active rolling search window (e.g. today .. +30 days) instead of stale historical dates.
 */
export function resolveFlyTargetUrl(
  url: string,
  isRolling = false,
  offsetDays = 0,
  windowDays = 30
): string {
  if (!url) return "";
  if (!isRolling) return url;

  try {
    const now = new Date();
    const startMin = new Date(now.getTime() + offsetDays * 86400000);

    const mDurHi = url.match(/durationTo=(\d+)/);
    const durHi = mDurHi ? parseInt(mDurHi[1], 10) : 8;

    let startMax: Date;
    let returnDate: Date;

    if (offsetDays > 0) {
      startMax = new Date(startMin.getTime() + windowDays * 86400000);
      returnDate = new Date(startMax.getTime() + durHi * 86400000);
    } else {
      returnDate = new Date(now.getTime() + windowDays * 86400000);
      const mDurLo = url.match(/durationFrom=(\d+)/);
      const durLo = mDurLo ? parseInt(mDurLo[1], 10) : 7;
      startMax = new Date(returnDate.getTime() - durLo * 86400000);
    }

    const fmt = (d: Date) => {
      const day = String(d.getDate()).padStart(2, "0");
      const month = String(d.getMonth() + 1).padStart(2, "0");
      const year = d.getFullYear();
      return `${day}-${month}-${year}`;
    };

    let res = url;
    if (res.includes("startDateMin=")) {
      res = res.replace(/startDateMin=[^&]*/, `startDateMin=${fmt(startMin)}`);
    } else if (res.includes("?")) {
      res += `&startDateMin=${fmt(startMin)}`;
    }
    if (res.includes("startDateMax=")) {
      res = res.replace(/startDateMax=[^&]*/, `startDateMax=${fmt(startMax)}`);
    } else if (res.includes("?")) {
      res += `&startDateMax=${fmt(startMax)}`;
    }
    if (res.includes("returnDate=")) {
      res = res.replace(/returnDate=[^&]*/, `returnDate=${fmt(returnDate)}`);
    } else if (res.includes("?")) {
      res += `&returnDate=${fmt(returnDate)}`;
    }
    return res;
  } catch (e) {
    return url;
  }
}
