#!/usr/bin/python
# based on http://roguebasin.roguelikedevelopment.org/index.php?title=PythonShadowcastingImplementation by Eric Burgess <ericdb@gmail.com>
"FOV calculation for roguelike"

import sys,random
import curses

FOV_RADIUS = 10
SAFE_DIST= 10
MOVE_KEYS={
	curses.KEY_LEFT: (-1, 0),
	curses.KEY_RIGHT:(+1, 0),
	curses.KEY_UP:   ( 0,-1),
	curses.KEY_DOWN: ( 0,+1),
	curses.KEY_HOME: (-1,-1),
	curses.KEY_PPAGE:(+1,-1),
	curses.KEY_NPAGE:(+1,+1),
	curses.KEY_END:  (-1,+1),
}
DIRECTION_TO_BEAM={
	(-1,-1):'\\',
	(+1,+1):'\\',
	(+1,-1):'/',
	(-1,+1):'/',
	( 0,+1):'|',
	( 0,-1):'|',
	(+1, 0):'-',
	(-1, 0):'-',
}


dungeon =  [
	"###########################################################",
	"#...........#.............................................#",
	"#...........#........#....................................#",
	"#.....................#...................................#",
	"#....####..............#..................................#",
	"#.......#.......................#####################.....#",
	"#.......#...........................................#.....#",
	"#.......#...........##..............................#.....#",
	"#####........#......##..........##################..#.....#",
	"#...#...................###.....#................#..#.....#",
	"#...#............#......#.......#................#..#.....#",
	"#.......................###.....#..###############..#.....#",
	"#...............................#...................#.....#",
	"#.................######........#...................#.....#",
	"#...............................#####################.....#",
	"#.........................................................#",
	"#.........................................................#",
	"###########################################################"
]


class GameOver(Exception):
	pass

class Map(object):
	# Multipliers for transforming coordinates to other octants:
	mult = [
				[1,  0,  0, -1, -1,  0,  0,  1],
				[0,  1, -1,  0,  0, -1,  1,  0],
				[0,  1,  1,  0,  0, -1, -1,  0],
				[1,  0,  0,  1, -1,  0,  0, -1]
			]
	
	def __init__(self, map):
		self.data = map
		self.width, self.height = len(map[0]), len(map)
		self.light = []
		self.seen  = []
		for i in range(self.height):
			self.light.append([0] * self.width)
			self.seen.append([0] * self.width)

		self.flag = 0
		self.color_dark=make_color(curses.COLOR_BLACK,curses.COLOR_BLACK,curses.A_BOLD)
		self.color_lit=make_color(curses.COLOR_WHITE,curses.COLOR_BLACK)
		self.color_unseen=make_color(curses.COLOR_BLACK,curses.COLOR_BLACK)
		self.color_player=make_color(curses.COLOR_WHITE,curses.COLOR_BLACK,curses.A_BOLD)
		self.color_mob=make_color(curses.COLOR_RED,curses.COLOR_BLACK)
		self.color_beam=make_color(curses.COLOR_BLUE,curses.COLOR_BLACK,curses.A_BOLD)
		self.status=''
	
	def square(self, x, y):
		return self.data[y][x]
	
	def blocked(self, x, y):
		return (x < 0 or y < 0
				or x >= self.width or y >= self.height
				or self.data[y][x] == "#")
	
	def lit(self, x, y):
		return self.light[y][x] == self.flag
	
	def set_lit(self, x, y):
		if 0 <= x < self.width and 0 <= y < self.height:
			self.light[y][x] = self.flag
			if self.flag:
				self.seen[y][x] = True

	def _cast_light(self, cx, cy, row, start, end, radius, xx, xy, yx, yy, id):
		"Recursive lightcasting function"
		if start < end:
			return
		radius_squared = radius*radius
		for j in range(row, radius+1):
			dx, dy = -j-1, -j
			blocked = False
			while dx <= 0:
				dx += 1
				# Translate the dx, dy coordinates into map coordinates:
				X, Y = cx + dx * xx + dy * xy, cy + dx * yx + dy * yy
				# l_slope and r_slope store the slopes of the left and right
				# extremities of the square we're considering:
				l_slope, r_slope = (dx-0.5)/(dy+0.5), (dx+0.5)/(dy-0.5)
				if start < r_slope:
					continue
				elif end > l_slope:
					break
				else:
					# Our light beam is touching this square; light it:
					if dx*dx + dy*dy < radius_squared:
						self.set_lit(X, Y)
					if blocked:
						# we're scanning a row of blocked squares:
						if self.blocked(X, Y):
							new_start = r_slope
							continue
						else:
							blocked = False
							start = new_start
					else:
						if self.blocked(X, Y) and j < radius:
							# This is a blocking square, start a child scan:
							blocked = True
							self._cast_light(cx, cy, j+1, start, l_slope,
											 radius, xx, xy, yx, yy, id+1)
							new_start = r_slope
			# Row is scanned; do next row unless last square was blocked:
			if blocked:
				break

	def do_fov(self, player):
		"Calculate lit squares from the given location and radius"
		self.flag += 1
		x,y=player.pos
		for oct in range(8):
			self._cast_light(x, y, 1, 1.0, 0.0, player.sight_radius,
							 self.mult[0][oct], self.mult[1][oct],
							 self.mult[2][oct], self.mult[3][oct], 0)
	
	def display(self, s, player,monsters,beams):
		"Display the map on the given curses screen (utterly unoptimized)"
		dark, lit, unseen = self.color_dark,self.color_lit,self.color_unseen
		player_attrib,mob,beam_attrib=self.color_player,self.color_mob,self.color_beam
		for x in range(self.width):
			for y in range(self.height):
				attr = lit if self.lit(x,y) else (dark if self.seen[y][x] else unseen)
				s.addstr(y, x, self.square(x,y), attr)
		for objlist,attrib in (
				([m for m in monsters if self.lit(*m.pos)],mob),
				(beams,beam_attrib),
				([player],player_attrib),
			):
			for obj in objlist:
				x,y=obj.pos
				s.addstr(y,x,obj.char,attrib)

		h,w=s.getmaxyx()
		hpmeter='HP: %d' % player.health
		s.addstr(h-1,0,self.status.ljust(w-1-len(hpmeter))+hpmeter,0)

		s.refresh()

	def pickEmptySpot(self):
		while True:
			w,h=self.width,self.height
			x,y=random.randint(0,w),random.randint(0,h)
			if not self.blocked(x,y):
				return (x,y)

def make_color(fg,bg,attr=0):
	global lastColor
	try:
		lastColor+=1
	except NameError:
		lastColor=1
	
	curses.init_pair(lastColor,fg,bg)
	return curses.color_pair(lastColor)|attr

class GameObject(object):
	def __init__(self,pos,world,char):
		self.pos=pos
		self.world=world
		self.char=char
		self.dead=False
	
	def tryMove(self,dpos,alternates=True):
		(x,y),(dx,dy),map=self.pos,dpos,self.world.map
		for (rx,ry) in ((dx,dy),)+(((dx,0),(0,dy)) if alternates else tuple()):
			if (rx,ry)==(0,0):
				continue
			nx,ny=x+rx,y+ry
			if not map.blocked(nx,ny):
				self.moveTo((nx,ny),(x,y))
				return True
		return False
	
	def dist(self,opos):
		x,y=self.pos
		ox,oy=opos
		return ((x-ox)**2+(y-oy)**2)**0.5
	
	def dist2(self,opos):
		x,y=self.pos
		ox,oy=opos
		return ((x-ox)**2+(y-oy)**2)
	
	def moveTo(self,newPos,oldPos):
		self.pos=newPos
	

class Player(GameObject):
	def __init__(self,pos,world):
		GameObject.__init__(self,pos,world,'@')
		self.last_pos=None
		self.sight_radius=15
		self.health=15
		self.lastMove=(0,-1)

	def hurt(self,damage,bywhat):
		self.health-=damage
		self.world.addMessage("You are hit by %s for %d damage!" % (bywhat,damage))
		if self.health<=0:
			self.dead=True
			self.world.addMessage("You die...")
	
	def tryMove(self,dpos,alternates=True):
		self.lastMove=dpos
		return GameObject.tryMove(self,dpos,alternates)
	
	def fire(self):
		self.world.beams.append(Beam(self.pos,self.world,self.lastMove))
	
	def moveTo(self,newPos,oldPos):
		mob=self.world.getAgent(newPos)
		if mob!=None:
			dmg=random.randint(1,2)
			mob.hurt(dmg,'the player')
			extra=' It dies.' if mob.dead else ''
			self.world.addMessage("You hit %s for %d damage.%s" % (mob.name,dmg,extra))
		else:
			self.pos=newPos

class Beam(GameObject):
	MAX_BOUNCES=5
	def __init__(self,pos,world,direction):
		GameObject.__init__(self,pos,world,DIRECTION_TO_BEAM[direction])
		self.direction=direction
		self.age=0
	def update(self):
		if self.dead:
			return
		while not self.tryMove(self.direction,alternates=False):
			self.age+=1
			if self.age<Beam.MAX_BOUNCES:
				self.direction=self.findNewDirection()
				self.char=DIRECTION_TO_BEAM[self.direction]
			else:
				self.dead=True
				return
		mon=self.world.getAgent(self.pos)
		if mon:
			mon.hurt(1,'a beam')
			self.dead=True
	
	def findNewDirection(self):
		dx,dy=self.direction
		x,y=self.pos
		map=self.world.map
		if map.blocked(x+dx,y):
			dx*=-1
		if map.blocked(x,y+dy):
			dy*=-1
		if (dx,dy)==self.direction: # hit a corner dead on
			dx*=-1
			dy*=-1
		return (dx,dy)


class Monster(GameObject):
	def __init__(self,pos,world):
		GameObject.__init__(self,pos,world,'z')
		self.run_threshold=random.randint(6,15)
		self.awake=False
		self.coward=False
		self.name='a monster'
		self.health=2
	
	def update(self):
		if self.dead:
			return
		world=self.world
		if self.awake:
			dpos=self.pickBestDirection(self.nearestPlayer)
			if dpos:
				self.tryMove(dpos)
		else:
			if self.dist(world.player.pos)<self.run_threshold:
				if self.world.map.lit(*self.pos): # hacky way to implement line of sight
					self.awake=True
					self.run_threshold=25 
					self.char='M'
	
	def pickBestDirection(self,keyfunc):
		x,y=self.pos
		positions=list(MOVE_KEYS.values())
		random.shuffle(positions) # the sort is stable, so this randomizes directions with the same distance
		mult = -1 if self.coward else +1
		positions.sort(key=lambda d:mult*keyfunc((x+d[0],y+d[1])))
		return positions[0]

	def nearestPlayer(self,pos):
		return self.world.player.dist2(pos)

	def moveTo(self,newPos,oldPos):
		if newPos==self.world.player.pos:
			self.world.player.hurt(random.randint(2,6),self.name)
		else:
			self.pos=newPos

	def hurt(self,amt,bywhat):
		self.health-=amt
		if self.health<=0:
			self.dead=True
			self.world.checkForWin()

class World(object):
	def __init__(self):
		self.map=map=Map(dungeon)
		self.player=Player((36,13),self)
		self.monsters=list(self.createMonsters())
		self.beams=[]
		self.messages=[]
		self.showingMore=False
		self.scheduled=[]
		self.gameOver=False
		self.noTurn=False

	def checkForWin(self):
		if all(mon.dead for mon in self.monsters):
			self.addMessage("All the monsters are dead!")
			self.addMessage("You return home a hero.")
			self.gameOver=True

	def createMonsters(self):
		map,player=self.map,self.player
		for _ in range(5):
			where=map.pickEmptySpot()
			while player.dist(where)<SAFE_DIST:
				where=map.pickEmptySpot()
			m=Monster(where,self)
			m.coward=random.choice((False,False,True))
			yield m
	
	def draw(self,screen):
		map=self.map
		if self.messages:
			self.showingMore=len(self.messages)>1
			map.status=self.messages[0]+(' (more)' if len(self.messages)>1 else '')
			self.messages=self.messages[1:]
		else:
			self.showingMore=False
		self.map.display(screen,self.player,self.monsters,self.beams)
	
	def update(self):
		if self.noTurn:
			return
		if self.gameOver:
			raise GameOver()
	
		player=self.player
		if player.dead:
			raise GameOver()
		if player.pos!=player.last_pos:
			player.last_pos=player.pos
			self.map.do_fov(player)
		
		self.updateAndCull(self.beams)
		self.updateAndCull(self.monsters)
		for func in self.scheduled:
			func()
		self.scheduled=[]
	
	def schedule(self,func):
		self.scheduled.append(func)

	def updateAndCull(self,existing):
		dead=[]
		for i,obj in enumerate(existing):
			obj.update()
			if obj.dead:
				dead.append(i)
		for i in dead[::-1]:
			existing[i:i+1]=[]

	def handleKey(self,key):
		self.noTurn=False
		if self.showingMore:
			self.noTurn=True
		else:
			if key == ord('q'):
				sys.exit()
			elif key in (ord(' '),ord('.')):
				pass
			elif key == ord('z'):
				self.player.fire()
			elif key in MOVE_KEYS:
				self.player.tryMove(MOVE_KEYS[key])
			else:
				self.noTurn=True
	
	def addMessage(self,msg):
		self.messages.append(msg)

	def getAgent(self,pos):
		for obj in self.monsters+[self.player]:
			if obj.pos==pos:
				return obj

if __name__=='__main__':	
	def main(screen):
		curses.curs_set(0)

		world=World()
		try:
			while True:
				world.update()
				world.draw(screen)
				world.handleKey(screen.getch())
		except GameOver:
			pass
	curses.wrapper(main)
