import {
  Apple,
  Beef,
  CakeSlice,
  Carrot,
  Cookie,
  Croissant,
  CupSoda,
  Drumstick,
  EggFried,
  Fish,
  type LucideIcon,
  Pizza,
  Salad,
  Soup,
  Sprout,
  UtensilsCrossed,
  Wheat,
} from 'lucide-react'

/**
 * The Food.com dataset ships no photography, so a recipe tile falls back to a
 * tinted gradient with a category glyph on it. The tint comes from the recipe
 * id and the glyph from its tags: two independent inputs, so two recipes of the
 * same kind still look different next to each other.
 */
export interface RecipeTint {
  /** Gradient start, top left. */
  from: string
  /** Gradient end, bottom right. */
  to: string
  /** Stroke colour for the glyph drawn on top. */
  ink: string
  /** Ready to drop into a `style={{ backgroundImage }}`. */
  gradient: string
}

function tint(from: string, to: string, ink: string): RecipeTint {
  return {
    from,
    to,
    ink,
    gradient: `linear-gradient(135deg, ${from} 0%, ${to} 100%)`,
  }
}

export const RECIPE_TINTS: readonly RecipeTint[] = [
  tint('#F9DCC8', '#EEB491', '#A9603A'),
  tint('#FCEDC6', '#F3D28E', '#A87D3C'),
  tint('#DCE8F4', '#AFCAE5', '#456A8D'),
  tint('#FADFE2', '#EDB5BD', '#A9535F'),
  tint('#DEECD9', '#B3D2AB', '#4C7B46'),
  tint('#EFE5D8', '#D7C3AB', '#7B654A'),
  tint('#E9DDF1', '#C6B1DE', '#6C4F8D'),
  tint('#D8EFE9', '#A8D8CB', '#3D7B6C'),
] as const

/**
 * Pure: the same recipe id always gets the same tint. The bit mixing keeps
 * consecutive ids from marching through the palette in visible order.
 */
export function hashId(id: number): RecipeTint {
  let hash = Number.isFinite(id) ? Math.trunc(Math.abs(id)) : 0

  hash = (hash ^ 61) ^ (hash >>> 16)
  hash = hash + (hash << 3)
  hash = hash ^ (hash >>> 4)
  hash = Math.imul(hash, 0x27d4eb2d)
  hash = hash ^ (hash >>> 15)

  return RECIPE_TINTS[Math.abs(hash) % RECIPE_TINTS.length]
}

interface CategoryRule {
  icon: LucideIcon
  keywords: readonly string[]
  /** Keywords that veto the rule even when one of `keywords` matched. */
  except?: readonly string[]
}

/**
 * Order matters: the specific categories are tested before the broad ones, so a
 * recipe tagged both `desserts` and `vegetarian` gets a cake and not a sprout.
 */
const CATEGORY_RULES: readonly CategoryRule[] = [
  {
    icon: CakeSlice,
    keywords: ['dessert', 'cake', 'pie', 'pudding', 'candy', 'ice-cream'],
    except: ['pancake', 'cupcake'],
  },
  { icon: Soup, keywords: ['soup', 'stew', 'chowder', 'broth', 'chili'] },
  {
    icon: CupSoda,
    keywords: ['beverage', 'drink', 'cocktail', 'smoothie', 'punch'],
  },
  { icon: Salad, keywords: ['salad', 'slaw'] },
  {
    icon: Fish,
    keywords: ['seafood', 'fish', 'salmon', 'shrimp', 'tuna', 'crab'],
  },
  { icon: Pizza, keywords: ['pizza'] },
  { icon: Wheat, keywords: ['pasta', 'noodle', 'spaghetti', 'lasagna'] },
  { icon: Croissant, keywords: ['bread', 'roll', 'muffin', 'scone', 'biscuit'] },
  { icon: Cookie, keywords: ['cookie', 'brownie', 'bar-cookie'] },
  {
    icon: EggFried,
    keywords: ['breakfast', 'brunch', 'egg', 'pancake', 'waffle', 'oatmeal'],
  },
  { icon: Drumstick, keywords: ['poultry', 'chicken', 'turkey', 'duck'] },
  { icon: Beef, keywords: ['beef', 'pork', 'meat', 'lamb', 'steak', 'bacon'] },
  { icon: Sprout, keywords: ['vegetarian', 'vegan'] },
  { icon: Apple, keywords: ['fruit', 'apple', 'berry', 'citrus', 'banana'] },
  { icon: Carrot, keywords: ['vegetable', 'veggie', 'potato', 'greens'] },
] as const

/** The glyph for a recipe, chosen from its tags. */
export function categoryIconFor(tags: readonly string[]): LucideIcon {
  const haystack = tags.join(' ').toLowerCase()

  for (const rule of CATEGORY_RULES) {
    if (rule.except?.some((keyword) => haystack.includes(keyword))) {
      continue
    }

    if (rule.keywords.some((keyword) => haystack.includes(keyword))) {
      return rule.icon
    }
  }

  return UtensilsCrossed
}
