// Package diamond: two exported functions reach the seed through private functions, and a third
// exported function calls both. NEAREST stops at Left and Right; ALL also reports Top.
package diamond

func sink() int { return 10 }

func left() int { return sink() }

func right() int { return sink() + 1 }

func Left() int { return left() }

func Right() int { return right() }

func Top() int { return Left() + Right() }
